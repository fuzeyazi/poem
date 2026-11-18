package com.fuze.potryservice.service.impl;

import cn.hutool.core.util.BooleanUtil;
import com.alibaba.fastjson.JSON;
import com.fuze.context.BaseContext;
import com.fuze.dto.*;
import com.fuze.entity.Poem;
import com.fuze.entity.UserJo;
import com.fuze.potryservice.config.RandomIdPool;
import com.fuze.potryservice.mapper.PoemLunTanMapper;
import com.fuze.potryservice.mapper.PotryMapper;
import com.fuze.potryservice.mapper.UserMapper;
import com.fuze.potryservice.service.PoemLunTanService;
import com.fuze.potryservice.service.PotryService;
import com.fuze.result.PageResult;
import com.fuze.result.Result;
import com.fuze.result.ScrollResult;
import com.fuze.vo.*;
import com.github.pagehelper.Page;
import com.github.pagehelper.PageHelper;
import com.github.pagehelper.PageInfo;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ZSetOperations;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;
import java.util.function.Supplier;
import java.util.stream.Collectors;

@Slf4j
@Service
public class PoemLunTanServiceimpl implements PoemLunTanService {
    @Autowired
    private PoemLunTanMapper poemLunTanMapper;
    @Autowired
    private RandomIdPool randomIdPool;
    @Autowired
    private org.springframework.transaction.support.TransactionTemplate transactionTemplate;
    @Autowired
    private UserMapper userMapper;
    @Autowired
    private PotryMapper potryMapper;
    @Autowired
    private StringRedisTemplate stringRedisTemplate;
    @Autowired
    private AsyncService asyncService;
    @Autowired
    private RabbitTemplate rabbitTemplate;
    @Transactional
    @Override
    public void fabu(PoemBlogDto poemBlogDto, Integer id) {
        log.info("标题：{}", poemBlogDto.getTitle());
        PoemBlogDtoPlus poemBlogDtoPlus = new PoemBlogDtoPlus();
        BeanUtils.copyProperties(poemBlogDto, poemBlogDtoPlus);
        poemBlogDtoPlus.setUserid(id);
        poemLunTanMapper.fabu12(poemBlogDtoPlus);   //insert回填bolgid
        //发帖事件改经RabbitMQ分发:事务提交后投递(避免消费者读到未提交数据),
        //消费者负责粉丝收件箱+帖子缓存+WebSocket实时推送;获得削峰/重试/解耦能力
        PoemBlogDtoPlus payload = poemBlogDtoPlus;
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                // afterCommit在请求线程执行,MDC中traceId仍可用,随消息透传给消费者串日志。
                // 投递失败不再让接口500(事务已提交、帖子已入库,500会造成"用户以为失败重发"的不一致):
                // 落入Redis补偿队列,由定时任务重投
                String traceId = org.slf4j.MDC.get("traceId");
                String json = JSON.toJSONString(payload);
                try {
                    rabbitTemplate.convertAndSend("post.exchange", "post.created", json, m -> {
                        if (traceId != null) {
                            m.getMessageProperties().setHeader("traceId", traceId);
                        }
                        return m;
                    });
                } catch (Exception e) {
                    log.error("发帖通知投递失败(broker不可用),进入补偿队列待重投", e);
                    try {
                        stringRedisTemplate.opsForList().leftPush(PENDING_NOTIFY_KEY, json);
                    } catch (Exception re) {
                        log.error("补偿记录亦失败(Redis不可用),该通知消息丢失,需人工核对帖子", re);
                    }
                }
            }
        });
    }

    @Override
    public PoemBlogVo selectxiangxi(Integer blogid) {
        Integer userid=poemLunTanMapper.getUserid(blogid);
        PoemBlogDtoSuper poemBlogDto = poemLunTanMapper.selectxiangxi(blogid);
        PoemBlogVo poemBlogVo = new PoemBlogVo();
        BeanUtils.copyProperties(poemBlogDto, poemBlogVo);
        String touxiang = userMapper.gettouxiangbyid(userid);
        String name = userMapper.getusernamebyid(userid);
        String nameTager = userMapper.getuserTagerbyid(poemBlogDto.getUserId());
        Integer fans = userMapper.getfans(userid);
        poemBlogVo.setTouxiang(touxiang);
        poemBlogVo.setUsername(name);
        poemBlogVo.setId(blogid);
        poemBlogVo.setNameTager(nameTager);
        poemBlogVo.setFans(fans);
        //一点进去就可以看自己是否有点赞
        isBlogLiked(poemBlogVo, blogid);
        return poemBlogVo;
    }

    private void isBlogLiked(PoemBlogVo poemBlogVo, Integer blogid) {
        Integer userid = BaseContext.getCurrentId().intValue();
        //判断当前登录用户是否已经点赞
        Double ismember = stringRedisTemplate.opsForZSet().score("blog:like" + blogid, userid.toString());
        if (ismember == null) {
            //如果未点赞，则返回false
            poemBlogVo.setBlogLike(false);
        } else {
            //如果已经点赞，则返回true
            poemBlogVo.setBlogLike(true);
        }
    }


    @Override
    public boolean dianzan(Integer blogid) {
        int userid = BaseContext.getCurrentId().intValue();
        return toggleLike("blog:like" + blogid, String.valueOf(userid),
                () -> poemLunTanMapper.insertBlogLike(userid, blogid),
                () -> poemLunTanMapper.deleteBlogLike(userid, blogid),
                () -> poemLunTanMapper.updatedianzan(blogid),
                () -> poemLunTanMapper.updatequxiaodianzan(blogid));
    }

    /**
     * 幂等点赞toggle。原实现"先ZSCORE查重再ZADD"两步非原子(并发首点全部超发),且判重仅存Redis
     * (Redis重启即丢,同用户可无限刷计数)。改造:
     * 1. 原子占位: 直接用ZADD返回值判断(单命令在Redis内串行执行),并发首点只有一个成功;
     * 2. 事实源: blog_like/comment_like复合主键明细表, INSERT IGNORE幂等, 计数列只在明细
     *    真正增删(affected>0)时同步更新 —— Redis丢数据时affected=0自动拦截重复计数,惰性自愈;
     * 3. 降级: Redis异常时直接走DB明细判重(同样幂等),点赞链路对Redis故障零感知。
     * DB事务回滚场景同样自愈: 占位残留但明细已回滚,下次取消时DELETE affected=0不扣计数。
     */
    private boolean toggleLike(String key, String member,
                               Supplier<Integer> insertDetail, Supplier<Integer> deleteDetail,
                               Runnable incCount, Runnable decCount) {
        try {
            boolean added = Boolean.TRUE.equals(stringRedisTemplate.opsForZSet()
                    .add(key, member, System.currentTimeMillis()));
            if (added) {
                return inTxWithDeadlockRetry(() -> {
                    if (insertDetail.get() > 0) {
                        incCount.run();
                    }
                    return true;
                });
            }
            if (stringRedisTemplate.opsForZSet().remove(key, member) > 0) {
                return inTxWithDeadlockRetry(() -> {
                    if (deleteDetail.get() > 0) {
                        decCount.run();
                    }
                    return false;
                });
            }
            return false;
        } catch (Exception e) {
            log.warn("点赞Redis异常,降级DB明细判重: key={}", key, e);
            return inTxWithDeadlockRetry(() -> {
                if (insertDetail.get() > 0) {
                    incCount.run();
                    return true;
                }
                if (deleteDetail.get() > 0) {
                    decCount.run();
                }
                return false;
            });
        }
    }

    /**
     * 编程式事务包住"明细+计数"两条写(原子), 并对 InnoDB 死锁(同user并发toggle时明细行锁
     * 与计数行锁成环,MySQL自动回滚victim)做重试 —— 重试体因 INSERT IGNORE/affected 判断
     * 天然幂等,重试必达一致状态。
     */
    private boolean inTxWithDeadlockRetry(java.util.function.Supplier<Boolean> body) {
        for (int attempt = 0; ; attempt++) {
            try {
                return Boolean.TRUE.equals(transactionTemplate.execute(status -> body.get()));
            } catch (org.springframework.dao.DeadlockLoserDataAccessException e) {
                if (attempt >= 4) {
                    throw e;
                }
                log.warn("点赞事务死锁,victim回滚后第{}次重试", attempt + 1);
                try {
                    Thread.sleep((attempt + 1) * 2L);   // 死锁窗口毫秒级,线性退避后重试基本必成
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    throw e;
                }
            }
        }
    }

    @Override
    public List<UserDianZanVo> dianzanrank(Integer blogid) {
        //1.查询top5的点赞用户
        String key = "blog:like" + blogid;
        //Zset是有序的
        Set<String> top5 = stringRedisTemplate.opsForZSet().range(key, 0, 4);
        //解析出用户id
        List<Integer> userIds = new ArrayList<>();
        if (top5 != null) {
            for (String s : top5) {
                try {
                    int userId = Integer.parseInt(s);
                    userIds.add(userId);
                } catch (NumberFormatException e) {
                    // 处理异常，例如记录日志或跳过该元素
                    System.err.println("无法将字符串 " + s + " 转换为整数");
                }
            }
        }else{
            return null;
        }
        List<UserDianZanVo> userDianZanVos = new ArrayList<>();
        //根据用户id查询
        if(userIds.isEmpty()){
            return userDianZanVos;
        }
        List<UserJo> user = userMapper.getuserbylistid(userIds);


            for (UserJo userJo : user) {
                UserDianZanVo userDianZanVo = new UserDianZanVo();
                userDianZanVo.setName(userJo.getName());
                userDianZanVo.setTouxiang(userJo.getTouxiang());
                userDianZanVos.add(userDianZanVo);
            }
            return userDianZanVos;

    }

    @Override
    public boolean isfrend(Integer followUserid) {
        Integer userid = BaseContext.getCurrentId().intValue();
        List<Integer> isuserList = poemLunTanMapper.isfrend11(followUserid, userid);
    // 如果列表为空，说明没有关系
    if (isuserList.isEmpty()) {
        return false;
    }
    // 如果列表中有值，说明有关系
    return true;
    }

    @Override
    @Transactional
    public Result guanzhu(Integer followUserid, boolean isFollow) {
        //判断是否是关注还是取关
        Integer userid = BaseContext.getCurrentId().intValue();
        if (isFollow) {
            //关注就新增关注
            poemLunTanMapper.insertguanzhu(followUserid, userid);
            poemLunTanMapper.addfans(followUserid);
            return Result.success("关注成功");
        } else {

            poemLunTanMapper.deleteguanzhu(followUserid, userid);
            poemLunTanMapper.deletefans(followUserid);
            return Result.success("取消关注");
        }
    }

    @Override
    public PageResult GetPoemPage(Integer pageNum, Integer pageSize, String type) {
        PageHelper.startPage(pageNum, pageSize);
        Page<PoemBlogVo> page = poemLunTanMapper.GetPoemPage(type);
        long total = page.getTotal();
        List<PoemBlogVo> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public BlogUserVo getByUsername(Integer followid) {
        return poemLunTanMapper.getByUsername1(followid);
    }

    @Override
    public PageResult selecttiezi(Integer pageNum, Integer pageSize, Integer followid) {
        PageHelper.startPage(pageNum, pageSize);
        Page<UserBlogListVo> page = poemLunTanMapper.selecttiezi(followid);
        long total = page.getTotal();
        List<UserBlogListVo> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public Result selectguanzhu(Long lasttimemax, Long offset) {
        //获取当前用户的收件箱
        Integer id = BaseContext.getCurrentId().intValue();
        String key = "fan:" + id;
        //1.查询当前用户的收件箱,lasttimemax上次的最小值，max最大值，offset偏移量，count数量
        Set<ZSetOperations.TypedTuple<String>> typedTuples = stringRedisTemplate.opsForZSet().reverseRangeByScoreWithScores(key, 0, lasttimemax, offset, 5);
        if (typedTuples == null || typedTuples.isEmpty()) {
            ScrollResult emptyResult = new ScrollResult();
            emptyResult.setList(new ArrayList<>());
            emptyResult.setOffset(0L);
            emptyResult.setMinTime(0L);
            return Result.success(emptyResult);
        }
        //解析typedTuples获取id，和分数
        List<Long> ids = new ArrayList<>(typedTuples.size());
        long mintime = 0;
        int os = 1;
        for (ZSetOperations.TypedTuple<String> tuple : typedTuples) {
            //获取博客id
            String idd = tuple.getValue();
            if (idd != null) {
                ids.add(Long.valueOf(idd));
            }
            //获取分数
            //获取offer,offer是上一次的最小值有多少个重复的
            long mintime1 = tuple.getScore().longValue();
            if (mintime == mintime1) {
                os++;
            } else {
                mintime = tuple.getScore().longValue();
                os = 1;
            }
        }
        //根据博客id查询对应的文章
        List<PoemBlogVo> blogListVos = poemLunTanMapper.selecttieziy(ids);
        log.info("博客信息：{}", blogListVos);
        for (PoemBlogVo blogListVo : blogListVos) {
            //判断是否点赞
            isBlogLiked(blogListVo, blogListVo.getId());
            //
        }
        //封装返回
        ScrollResult r = new ScrollResult();
        r.setList(blogListVos);
        r.setOffset((long) os);
        r.setMinTime(mintime);

        return Result.success(r);
    }

    @Override
    @Transactional
    public Result fabucomment(FourmCommentDto fourmCommentDto, Integer id) {
        Integer parentId = fourmCommentDto.getParentId();
        int rootId = (parentId == null) ? -1 : parentId;
        Integer replyToUser = null;
        if (rootId != -1) {
            //拍扁归一:回复"回复"时挂到根评论下并记录被回复人,避免两级组装丢失第三级
            FabaCommnetVo parent = poemLunTanMapper.getCommentById(rootId);
            if (parent == null) {
                return Result.error("被回复的评论不存在");
            }
            replyToUser = parent.getUserId();
            if (parent.getParentId() != null && parent.getParentId() != -1) {
                rootId = parent.getParentId();
            }
            poemLunTanMapper.addcomment(rootId);
        }
        fourmCommentDto.setParentId(rootId);
        poemLunTanMapper.fabucomment(fourmCommentDto, id, replyToUser);
        poemLunTanMapper.addblogcomment(fourmCommentDto.getBlogId());
        return Result.success("发布成功");
    }

    @Override
    public List<FabaCommnetVo> selectConmmets(Integer blogid) {
        //两段式加载:主评论最新20条(走idx_blog_id)+子评论批量IN,替代全量拉回内存组树
        List<FabaCommnetVo> mainComments = poemLunTanMapper.selectMainComments(blogid);
        if (mainComments == null || mainComments.isEmpty()) {
            return Collections.emptyList();
        }
        List<Integer> mainIds = mainComments.stream().map(FabaCommnetVo::getId).toList();
        List<FabaCommnetVo> allChildren = poemLunTanMapper.selectChildComments(mainIds);
        Map<Integer, List<FabaCommnetVo>> childCommentsMap = allChildren.stream()
                .filter(c -> c.getParentId() != null)
                .collect(Collectors.groupingBy(FabaCommnetVo::getParentId));
        for (FabaCommnetVo mainComment : mainComments) {
            mainComment.setChildren(childCommentsMap.getOrDefault(mainComment.getId(), Collections.emptyList()));
        }
        return mainComments;
    }
@Override
    public boolean commentdianzan(Integer commentid) {
        int userid = BaseContext.getCurrentId().intValue();
        return toggleLike("comment:like" + commentid, String.valueOf(userid),
                () -> poemLunTanMapper.insertCommentLike(userid, commentid),
                () -> poemLunTanMapper.deleteCommentLike(userid, commentid),
                () -> poemLunTanMapper.updatedianzan1(commentid),
                () -> poemLunTanMapper.updatequxiaodianzan1(commentid));
    }

  @Override
public PageResult selectConmmets1(Integer blogid, Integer pageNum, Integer pageSize) {
    // 只对父评论进行分页
    PageHelper.startPage(pageNum, pageSize);
    //查询父评论的id
    List<FabaCommnetVo> mainComments = poemLunTanMapper.selectMainComments(blogid);

    // 获取分页信息
    PageInfo<FabaCommnetVo> pageInfo = new PageInfo<>(mainComments);

    // 构建子评论映射
    List<Integer> mainCommentIds = mainComments.stream()
            .map(FabaCommnetVo::getId)
            .collect(Collectors.toList());

    List<FabaCommnetVo> allChildComments = poemLunTanMapper.selectChildComments(mainCommentIds);

    Map<Integer, List<FabaCommnetVo>> childCommentsMap = allChildComments.stream()
            .collect(Collectors.groupingBy(FabaCommnetVo::getParentId));

    // 为每个主评论设置子评论
    for (FabaCommnetVo mainComment : mainComments) {
        List<FabaCommnetVo> childComments = childCommentsMap.getOrDefault(mainComment.getId(), Collections.emptyList());
        mainComment.setChildren(childComments);
    }

    // 返回分页结果
    return new PageResult(pageInfo.getTotal(), mainComments);
}

    @Override
    public List<PoemBlogVo> selectforum() {
        return null;
    }

    @Override
    public List<BlogVO> selectforum1() {
        List<Integer> ids = randomIdPool.randomIds(RandomIdPool.BLOG_POOL, 5, poemLunTanMapper::GetAllBlogIds);
        return ids.isEmpty() ? poemLunTanMapper.selectforum1() : poemLunTanMapper.GetBlogsByIds(ids);
    }

    @Override
    public List<PoemSerchVo> search(String content) {
        // ≥2字走FULLTEXT ngram短语索引, 单字(ngram_token_size=2无法切词)回退LIKE
        return PotryServiceImpl.useFullText(content)
                ? potryMapper.serchFt(PotryServiceImpl.ftPhrase(content))
                : potryMapper.serch(content);
    }



    /** 发帖通知投递失败补偿队列(Redis list, lpush+rightPop=FIFO) */
    public static final String PENDING_NOTIFY_KEY = "mq:pending:post.notify";

    /**
     * 补偿重投: 每20s扫描补偿队列,Rabbit恢复后逐条重投;消费端幂等键保证重投不重复触达
     */
    @org.springframework.scheduling.annotation.Scheduled(fixedDelay = 20000)
    public void republishPendingPostNotify() {
        while (true) {
            String json;
            try {
                json = stringRedisTemplate.opsForList().rightPop(PENDING_NOTIFY_KEY);
            } catch (Exception e) {
                return;   // Redis不可用,下轮再试
            }
            if (json == null) {
                return;
            }
            try {
                rabbitTemplate.convertAndSend("post.exchange", "post.created", json);
                log.info("补偿重投成功: {}", json.substring(0, Math.min(80, json.length())));
            } catch (Exception e) {
                try {
                    stringRedisTemplate.opsForList().rightPush(PENDING_NOTIFY_KEY, json);
                } catch (Exception ignore) {
                }
                log.warn("broker仍不可用,补偿消息留待下轮");
                return;
            }
        }
    }

}