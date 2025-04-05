package com.fuze.potryservice.service.impl;

import cn.hutool.core.util.BooleanUtil;
import com.fuze.context.BaseContext;
import com.fuze.dto.*;
import com.fuze.entity.Poem;
import com.fuze.entity.UserJo;
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
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ZSetOperations;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;
import java.util.stream.Collectors;

@Slf4j
@Service
public class PoemLunTanServiceimpl implements PoemLunTanService {
    @Autowired
    private PoemLunTanMapper poemLunTanMapper;
    @Autowired
    private UserMapper userMapper;
    @Autowired
    private PotryMapper potryMapper;
    @Autowired
    private StringRedisTemplate stringRedisTemplate;

    @Transactional
    @Override
    public void fabu(PoemBlogDto poemBlogDto, Integer id) {
        log.info("标题：{}", poemBlogDto.getTitle());
        //查询文章作者的粉丝ids
        List<Integer> userIds = poemLunTanMapper.getuseridbylistid(id);
        //发布完后，直接获取blogid
        PoemBlogDtoPlus poemBlogDtoPlus = new PoemBlogDtoPlus();
        BeanUtils.copyProperties(poemBlogDto, poemBlogDtoPlus);
        poemBlogDtoPlus.setUserid(id);
        poemBlogDtoPlus.setBolgid(0);
        poemLunTanMapper.fabu12(poemBlogDtoPlus);
        if (userIds.isEmpty()) {
            return;
        }
        //循环遍历，给每一个粉丝发送消息
        for (Integer userId : userIds) {
            //推送粉丝的id
            String key = "fan:" + userId;
            stringRedisTemplate.opsForZSet().add(key, String.valueOf(poemBlogDtoPlus.getBolgid()), System.currentTimeMillis());
        }
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
        Integer userid = BaseContext.getCurrentId().intValue();
        //判断当前登录用户是否已经点赞
        Double ismember = stringRedisTemplate.opsForZSet().score("blog:like" + blogid, userid.toString());
        if (ismember == null) {
            //如果未点赞则点赞
            poemLunTanMapper.updatedianzan(blogid);
            //点赞后,存到redis里面
            stringRedisTemplate.opsForZSet().add("blog:like" + blogid, userid.toString(), System.currentTimeMillis());
            return true;
//            stringRedisTemplate.opsForSet().add("blog"+blogid,userid.toString());
        } else {
            //如果已经点赞，则取消点赞
            poemLunTanMapper.updatequxiaodianzan(blogid);
            //取消点赞后，从redis里面移除
            stringRedisTemplate.opsForZSet().remove("blog:like" + blogid, userid.toString());
            return false;
        }
        //如果已经点赞，则取消点赞
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
        if (typedTuples != null) {
            return Result.success("压根没有关注任何人");
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
    public Result fabucomment(FourmCommentDto fourmCommentDto, Integer id) {
        if(fourmCommentDto.getParentId()!=-1){
            poemLunTanMapper.addcomment(fourmCommentDto.getParentId());
        }
        poemLunTanMapper.fabucomment(fourmCommentDto, id);
        poemLunTanMapper.addblogcomment(fourmCommentDto.getBlogId());
        return Result.success("发布成功");
    }

    @Override
    public List<FabaCommnetVo> selectConmmets(Integer blogid) {
        // 根据blogid将这个博客下所有的评论查出来
        List<FabaCommnetVo> allComments = poemLunTanMapper.selectConmme1t1(blogid);

        // 筛选出主评论，主评论的parentId为-1
        List<FabaCommnetVo> mainComments = allComments.stream()
                .filter(comment -> comment.getParentId() == -1)
                .toList();

        // 构建子评论映射
        Map<Integer, List<FabaCommnetVo>> childCommentsMap = allComments.stream()
                .filter(comment -> comment.getParentId() != -1)
                .collect(Collectors.groupingBy(FabaCommnetVo::getParentId));

        // 为每个主评论设置子评论
        for (FabaCommnetVo mainComment : mainComments) {
            List<FabaCommnetVo> childComments = childCommentsMap.getOrDefault(mainComment.getId(), Collections.emptyList());
            mainComment.setChildren(childComments);
        }

        return mainComments;
    }
@Override
    public boolean commentdianzan(Integer commentid) {
        Integer userid = BaseContext.getCurrentId().intValue();
        //判断当前登录用户是否已经点赞
        Double ismember = stringRedisTemplate.opsForZSet().score("comment:like" + commentid, userid.toString());
        if (ismember == null) {
            //如果未点赞则点赞
            poemLunTanMapper.updatedianzan1(commentid);
            //点赞后,存到redis里面
            stringRedisTemplate.opsForZSet().add("comment:like" + commentid, userid.toString(), System.currentTimeMillis());
            return true;
//            stringRedisTemplate.opsForSet().add("blog"+blogid,userid.toString());
        } else {
            //如果已经点赞，则取消点赞
            poemLunTanMapper.updatequxiaodianzan1(commentid);
            //取消点赞后，从redis里面移除
            stringRedisTemplate.opsForZSet().remove("comment:like" + commentid, userid.toString());
            return false;
        }

        //如果已经点赞，则取消点赞
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
        return poemLunTanMapper.selectforum1();
    }

    @Override
    public List<PoemSerchVo> search(String content) {
        return potryMapper.serch(content);
    }


}