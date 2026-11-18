package com.fuze.potryservice.service.impl;

import com.fuze.potryservice.cache.MultiLevelCacheManager;

import cn.hutool.core.util.BooleanUtil;
import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONUtil;
import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.JSONObject;
import com.fuze.context.BaseContext;
import com.fuze.entity.Poem;
import com.fuze.entity.Writer;
import com.fuze.entity.WriterEndVo;
import com.fuze.potryservice.config.RandomIdPool;
import com.fuze.potryservice.mapper.PotryMapper;
import com.fuze.potryservice.mapper.WriterMapper;
import com.fuze.potryservice.service.PotryService;

import com.fuze.response.RedisData;
import com.fuze.result.PageResult;
import com.fuze.vo.*;
import com.github.pagehelper.Page;
import com.github.pagehelper.PageHelper;
import com.github.pagehelper.PageInfo;
import jakarta.annotation.PreDestroy;
import lombok.extern.slf4j.Slf4j;
import org.redisson.Redisson;
import org.redisson.api.RBucket;
import org.redisson.api.RedissonClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadLocalRandom;
import java.util.function.Function;
import java.util.function.Supplier;
import java.util.concurrent.TimeUnit;
@Slf4j
@Service
public class PotryServiceImpl implements PotryService {
    @Autowired
    private PotryMapper potryMapper;
    @Autowired
    private WriterMapper writerMapper;
    @Autowired
    private RandomIdPool randomIdPool;
    @Autowired
    private StringRedisTemplate stringRedisTemplate;
    @Autowired
    private RedissonClient redissonClient;
    @Autowired
    private MultiLevelCacheManager multiLevelCacheManager;

    private final ExecutorService executorService = Executors.newSingleThreadExecutor();
    @Override
    public Integer getcount() {
        return cacheWithResilience("potry:count",
                s -> Integer.valueOf(s),
                () -> potryMapper.getcount());
    }

    @Override
    public List<String> GetAllDynasty() {
        return cacheWithResilience("potry:allDynasty",
                s -> JSONUtil.toList(s, String.class),
                () -> potryMapper.Getdynasty());
    }

    @Override
    public List<DynatryPoemResultVO> GetDynastyPoemResulVo() {
        return cacheWithResilience("potry:dynastyAgg",
                s -> JSONUtil.toList(s, DynatryPoemResultVO.class),
                () -> potryMapper.GetDynastyPoemResulVo());
    }

    /**
     * 聚合缓存三防护(静态语料聚合值):
     * 击穿—逻辑过期+setIfAbsent互斥,过期后抢锁者异步重建,期间返回旧值;缓存缺失时抢锁者同步回源,其余短等重读
     * 雪崩—逻辑过期TTL随机抖动(10±3分钟),且Redis任何异常降级DB直查保可用
     */
    private <T> T cacheWithResilience(String key, Function<String, T> parser, Supplier<T> dbLoader) {
        String json;
        try {
            json = stringRedisTemplate.opsForValue().get(key);
        } catch (Exception e) {
            log.warn("Redis不可用,降级DB: {}", key, e);
            return dbLoader.get();
        }
        try {
            if (json != null) {
                RedisData rd = JSONObject.parseObject(json, RedisData.class);
                String data = JSONObject.toJSONString(rd.getData());
                if (rd.getExpireTime().isAfter(LocalDateTime.now())) {
                    return parser.apply(data);
                }
                String asyncLockToken = acquireLock("lock:" + key);
                if (asyncLockToken != null) {
                    executorService.submit(() -> {
                        try {
                            saveAggregate(key, dbLoader.get());
                        } catch (Exception ex) {
                            log.warn("异步重建失败: {}", key, ex);
                        } finally {
                            unLock("lock:" + key, asyncLockToken);
                        }
                    });
                }
                return parser.apply(data);
            }
            String syncLockToken = acquireLock("lock:" + key);
            if (syncLockToken != null) {
                try {
                    T value = dbLoader.get();
                    saveAggregate(key, value);
                    return value;
                } finally {
                    unLock("lock:" + key, syncLockToken);
                }
            }
            Thread.sleep(50);
            json = stringRedisTemplate.opsForValue().get(key);
            if (json != null) {
                return parser.apply(JSONObject.toJSONString(JSONObject.parseObject(json, RedisData.class).getData()));
            }
            return dbLoader.get();
        } catch (Exception e) {
            log.warn("缓存处理异常,降级DB: {}", key, e);
            return dbLoader.get();
        }
    }

    /** 聚合值写入:逻辑过期包装 + TTL随机抖动防大量key同时到期 */
    private void saveAggregate(String key, Object value) {
        RedisData rd = new RedisData();
        rd.setData(value);
        rd.setExpireTime(LocalDateTime.now().plusMinutes(10)
                .plusSeconds(ThreadLocalRandom.current().nextInt(180)));
        stringRedisTemplate.opsForValue().set(key, JSONUtil.toJsonStr(rd));
    }

    @Override
    public List<String> GetAllPoemName() {
        return potryMapper.GetAllPoemName();
    }

    @Override
    public Poem GetContentById(Integer id) {
        if (id == null) return null;
        // 接入多级缓存架构：布隆过滤器防穿透 -> L1 Caffeine 本地毫秒读 -> L2 Redis 逻辑过期防击穿 -> DB 回源双写
        return multiLevelCacheManager.getPoem(id.longValue(), () -> {
            Poem poem = potryMapper.GetContentById(id);
            if (poem != null) {
                processPoemContent(poem);
            }
            return poem;
        });
    }

    /** 静默解析Poem;失败返回null由调用方决定重建 */
    private Poem parsePoemQuietly(String data) {
        try {
            return JSONObject.parseObject(data, Poem.class);
        } catch (Exception e) {
            return null;
        }
    }

    private Poem loadAndCachePoem(Integer id, String poemkey) {
        long idd=BaseContext.getCurrentId();

        Poem poem = potryMapper.GetContentById(id);
        if (poem != null) {
            processPoemContent(poem);
            RedisData redisData = new RedisData();
            redisData.setData(poem);
            redisData.setExpireTime(LocalDateTime.now().plusMinutes(1));
            stringRedisTemplate.opsForValue().set(poemkey, JSONUtil.toJsonStr(redisData));
        } else {
            //空值缓存:不存在的id写入短TTL占位,防止穿透反复打DB
            try {
                stringRedisTemplate.opsForValue().set(poemkey, "NULL", 2, TimeUnit.MINUTES);
            } catch (Exception e) {
                log.warn("空值缓存写入失败(降级流程): {}", id, e);
            }
        }
        return poem;
    }

    private void processPoemContent(Poem poem) {
        String content = poem.getContent();
        String remarks = poem.getRemarks();
        String translation = poem.getTranslation();
        String shangxi = poem.getShangxi();

        if (content != null) {
            content = content.replace("\r\n", "<br>");
        }
        if (remarks != null) {
            remarks = remarks.replace("\r\n", "<br>");
        }
        if (translation != null) {
            translation = translation.replace("\r\n", "<br>");
        }
        if (shangxi != null) {
            shangxi = shangxi.replace("\r\n", "<br>");
        }

        poem.setShangxi(shangxi);
        poem.setContent(content);
        poem.setRemarks(remarks);
        poem.setTranslation(translation);
    }

    @Override
    public List<PoemDataVo> GetPoemDataVoByDynasty(String dynasty) {
        return potryMapper.GetPoemDataVoByDynasty(dynasty);
    }

    @Override
    public List<PoemDataVo> GetPoemDateRondom() {
        return getPoemsByRandom(10);
    }

    /**
     * Redis随机id池(SRANDMEMBER) + 主键IN查询,替代 ORDER BY RAND() 的全表扫描+filesort;
     * 池为空(首次访问/过期)时回源装载全部id, 池1小时过期自愈; Redis异常降级回RAND()
     */
    private List<PoemDataVo> getPoemsByRandom(int n) {
        List<Integer> ids = randomIdPool.randomIds(RandomIdPool.POTRY_POOL, n, potryMapper::GetAllIds);
        return ids.isEmpty() ? potryMapper.GetPoemDateRondom() : potryMapper.GetPoemsByIds(ids);
    }

    @Override
    public PageResult GetPoemDataVoByWriter1(int pageNum, int pageSize, String name) {
        return null;
    }

    @Override
    public PageResult GetPoemPage(Integer pageNum, Integer pageSize) {
        // 1. 获取当前用户ID（根据你的业务需求决定是否使用）
        Long currentUserId = BaseContext.getCurrentId();

        // 2. 分页查询诗歌数据
        PageHelper.startPage(pageNum, pageSize);
        Page<PoemDataVo> page =  potryMapper.GetPoemvoByPage1();

        // 3. 批量获取当前用户点赞的诗歌ID集合
        Set<Integer> likedPoemIds = new HashSet<>(potryMapper.GetLike(currentUserId));

        // 4. 一次性设置点赞状态
        page.getResult().forEach(poem -> {
            poem.setIslike(likedPoemIds.contains(poem.getId()) ? "true" : "false");
        });

        // 5. 返回分页结果
        return new PageResult(page.getTotal(), page.getResult());
    }

    @Override
    public List<PoemVo> GetPoemBydynasty(String dynasty) {
        return potryMapper.GetPoemBydynasty(dynasty);
    }

    @Override
    public PageResult GetPoemBydynastys(Integer pageNum, Integer pageSize, String dynasty) {
        PageHelper.startPage(pageNum, pageSize);
        Page<PoemVo> page=potryMapper.GetPoemBydynasty(dynasty);
        long total = page.getTotal();
        List<PoemVo> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public PageResult GetPoemByType(Integer pageNum, Integer pageSize, String type) {
        PageHelper.startPage(pageNum, pageSize);
        Page<PoemDataVo> page=potryMapper.GetPoemByType(type);
        long total = page.getTotal();
        List<PoemDataVo> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public PageResult GetwriterBydynasty(Integer pageNum, Integer pageSize, String dynasty) {
        PageHelper.startPage(pageNum, pageSize);
        Page<Writer> page=potryMapper.GetwriterBydynasty(dynasty);
        long total = page.getTotal();
        List<Writer> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public PageResult GetwriterBydynasty11(Integer pageNum, Integer pageSize, String writer) {
        PageHelper.startPage(pageNum, pageSize);
        Page<PoemDataVo> page=potryMapper.GetwriterBywriter(writer);
        long total = page.getTotal();
        List<PoemDataVo> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public PageResult GetwriterBydynasty111(Integer pageNum, Integer pageSize, String writer) {
        PageHelper.startPage(pageNum,pageSize);
        Page<RhesisDataVo> page=potryMapper.GetwriterBywriter1(writer);
        long total = page.getTotal();
        List<RhesisDataVo> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public List<Poem> GetContentBytitle1(Integer id) {
        String pomekey="poem:"+"context:"+id;
        String redisdata=stringRedisTemplate.opsForValue().get(pomekey);
        RedisData redisData=new RedisData();
        if(redisdata==null){
            Poem poem=potryMapper.GetContentById(id);
            redisData.setData(poem);
            redisData.setExpireTime(LocalDateTime.now().plusMinutes(30));
            stringRedisTemplate.opsForValue().set(pomekey, JSONUtil.toJsonStr(redisData));
            if(poem.getRemarks()==null|| poem.getRemarks().isEmpty()){
                poem.setRemarks("暂时没有收录");
            }
            if(poem.getTranslation()==null|| poem.getTranslation().isEmpty()){
                poem.setTranslation("暂时没有收录");
            }
            if(poem.getShangxi()==null|| poem.getShangxi().isEmpty()){
                poem.setShangxi("暂时没有收录");
            }
            String content = poem.getContent();
            content = content.replace("\r\n", "<br>");
            poem.setContent(content);
            long currentUserId = BaseContext.getCurrentId();
            Set<Integer> likedPoemIds = new HashSet<>(potryMapper.GetLike(currentUserId));
            for(Integer poem1:likedPoemIds){
                if(poem1==id){
                    poem.setIslike("true");
                }
            }
            return Arrays.asList(poem);
        }else{
            String json = stringRedisTemplate.opsForValue().get(pomekey);
            RedisData deserializedRedisData = JSONObject.parseObject(json, RedisData.class);
            LocalDateTime expireTime = deserializedRedisData.getExpireTime();
            if (expireTime.isAfter(LocalDateTime.now())) {
                Poem poem = JSONObject.parseObject(JSONObject.toJSONString(deserializedRedisData.getData()), Poem.class);
                return Collections.singletonList(poem);
            }else{
                String lockKey = "lock:shop:" + id;
                String lockToken = acquireLock(lockKey);
                if (lockToken != null) {
                    executorService.submit(() -> {
                        try {
                            Poem poem = potryMapper.GetContentById(id);
                            redisData.setData(poem);
                            redisData.setExpireTime(LocalDateTime.now().plusMinutes(30));
                            stringRedisTemplate.opsForValue().set(pomekey, JSONUtil.toJsonStr(redisData));
                        } finally {
                            unLock(lockKey, lockToken);
                        }
                    });
                }
                Poem poem = JSONObject.parseObject(JSONObject.toJSONString(deserializedRedisData.getData()), Poem.class);
                return Collections.singletonList(poem);
            }

        }
    }

    @Override
    public PageResult GetPoembyTitle(Integer pageNum, Integer pageSize, String title) {
        recordHotSearch(title);
        PageHelper.startPage(pageNum, pageSize);
        // ≥2字走FULLTEXT ngram短语索引, 单字(ngram_token_size=2无法切词)回退LIKE
        Page<Poem> page = useFullText(title)
                ? potryMapper.GetPoembyTitleFt(ftPhrase(title))
                : potryMapper.GetPoembyTitle(title);
        long total = page.getTotal();
        List<Poem> records = page.getResult();
        return new PageResult(total, records);
    }

    static boolean useFullText(String kw) {
        return kw != null && kw.trim().length() >= 2;
    }

    /** BOOLEAN MODE 短语化: 双引号包裹令bigram相邻匹配(等价LIKE子串语义), 剥离用户输入中的引号防语法注入 */
    static String ftPhrase(String kw) {
        return "\"" + kw.replace("\"", "").trim() + "\"";
    }

    @Override
    public PageResult GetwriterB(Integer pageNum, Integer pageSize, String title) {
        PageHelper.startPage(pageNum, pageSize);
        Page<RhesisDataVo> page=potryMapper.GetwriterB(title);
        long total = page.getTotal();
        List<RhesisDataVo> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public String getcountbyid(int id)  {
        return potryMapper.getcountbyid(id);
    }
    @Override
    public void update(Integer userid,Integer poemid) {
        potryMapper.update(userid,poemid);
    }
    @Override
    public List<Writer> GetRondWriter11(String name) {
        return potryMapper.GetRondWriter11(name);
    }

    @Override
    public PageResult GetwriterBydynasty22(Integer pageNum, Integer pageSize) {
        // writer随机id池抽 pageSize 个诗人, 卡片按主键IN回表(朝代走potry.writer索引子查询);
        // 原实现为 writer×potry JOIN + DISTINCT + ORDER BY RAND() 全量filesort
        List<Integer> ids = randomIdPool.randomIds(RandomIdPool.WRITER_POOL, pageSize, writerMapper::selectAllWriterIds);
        if (!ids.isEmpty()) {
            List<Writer> records = writerMapper.selectWriterCardsByIds(ids);
            return new PageResult(writerMapper.getWriterCount(), records);
        }
        PageHelper.startPage(pageNum, pageSize);
        Page<Writer> page = potryMapper.GetRondWriter1();
        long total = page.getTotal();
        List<Writer> records = page.getResult();
        return new PageResult(total, records);

    }

    @Override
    public PageResult GetPoemDataVoByWriter(Integer pageNum, Integer pageSize, String name) {
        PageHelper.startPage(pageNum, pageSize);
        Page<PoemDataVo> page=potryMapper.GetPoemData(name);
        long total = page.getTotal();
        List<PoemDataVo> records = page.getResult();
        return new PageResult(total, records);
    }


    @Override
    public List<String> GetType() {
        List<String> list1=potryMapper.GetType();
        list1.removeIf(String::isEmpty);
        return list1;
    }
    @Override
    public List<PoemDataVo> GetPoemDataByType(String type) {
        return potryMapper.GetPoemDataByType(type);
    }
    @Override
    public List<Poem>  GetContentBytitle(String title) {
        return potryMapper.GetContentByTitle(title);
    }
    /** 挽词/悼亡类标题不适配"今日推荐"氛围(如《杨待制挽词》),命中即重抽 */
    private static boolean elegiacTitle(String title) {
        if (title == null) {
            return false;
        }
        return title.contains("挽") || title.contains("悼") || title.contains("祭")
                || title.contains("墓") || title.contains("葬") || title.contains("诔");
    }

    @Override
    public PoemDataVo GetVeryGoodPoem() {
        PoemDataVo picked = null;
        for (int i = 0; i < 4; i++) {   // 池9千余首,挽词占比小,几乎必中正常诗
            List<PoemDataVo> list = getPoemsByRandom(1);
            if (list.isEmpty()) {
                return null;
            }
            picked = list.get(0);
            if (!elegiacTitle(picked.getTitle())) {
                return picked;
            }
            log.info("今日推荐命中挽词《{}》,重抽", picked.getTitle());
        }
        return picked;   // 兜底:重试穷尽返回最后一次结果
    }
    private static final String UNLOCK_LUA_SCRIPT =
            "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end";

    private String acquireLock(String key) {
        String token = UUID.randomUUID().toString();
        Boolean success = stringRedisTemplate.opsForValue().setIfAbsent(key, token, 10, TimeUnit.SECONDS);
        return BooleanUtil.isTrue(success) ? token : null;
    }

    private boolean trylock(String key) {
        return acquireLock(key) != null;
    }

    private void unLock(String key, String token) {
        if (token == null || key == null) {
            return;
        }
        stringRedisTemplate.execute(
                new DefaultRedisScript<>(UNLOCK_LUA_SCRIPT, Long.class),
                Collections.singletonList(key),
                token
        );
    }

    private void unLock(String key) {
        stringRedisTemplate.delete(key);
    }
    @Override
    public WriterEndVo GetPoemWriter(int id) throws InterruptedException {
        // 接入多级缓存：布隆防穿透 + L1 Caffeine + L2 Redis + 规避递归与忙等
        return multiLevelCacheManager.getWriter(id, () -> {
            List<WriterEndVo> writerEndVo1 = potryMapper.GetPoemWriter1(id);
            if (writerEndVo1 == null || writerEndVo1.isEmpty()) {
                return null;
            }
            String dynasty = writerEndVo1.get(0).getDynasty();
            if (writerEndVo1.size() > 1) {
                for (int i = 1; i < writerEndVo1.size(); i++) {
                    dynasty = writerEndVo1.get(i).getDynasty() + ',' + dynasty;
                }
            }
            writerEndVo1.get(0).setDynasty(dynasty);
            return writerEndVo1.get(0);
        });
    }

    @PreDestroy
    public void destroy() {
        if (executorService != null) {
            executorService.shutdown();
        }
    }


    // ==================== 搜索建议 + 热搜榜(2026-10-25) ====================

    /** 补全词库ZSet: score恒0保证字典序, rangeByLex按前缀范围查询 */
    private static final String SUGGEST_ZSET = "poetry:suggest:zset";
    private static final String HOT_ZSET = "poetry:hotsearch";

    @Override
    public List<String> suggest(String kw) {
        if (kw == null || kw.isBlank()) {
            return Collections.emptyList();
        }
        String prefix = kw.trim();
        try {
            Long size = stringRedisTemplate.opsForZSet().zCard(SUGGEST_ZSET);
            if (size == null || size == 0) {
                loadSuggestDict();
            }
            // [prefix, prefix+￿] 字典序闭区间 = 全部以prefix开头的词
            Set<String> hits = stringRedisTemplate.opsForZSet().rangeByLex(SUGGEST_ZSET,
                    org.springframework.data.domain.Range.from(
                            org.springframework.data.domain.Range.Bound.inclusive(prefix)).to(
                            org.springframework.data.domain.Range.Bound.inclusive(prefix + '￿')),
                    org.springframework.data.redis.connection.RedisZSetCommands.Limit.limit().count(8));
            return hits == null ? Collections.emptyList() : new ArrayList<>(hits);
        } catch (Exception e) {
            log.warn("suggest词库异常,降级DB前缀查询: {}", e.getMessage());
            List<String> fallback = new ArrayList<>(potryMapper.GetTitlePrefix(prefix));
            fallback.addAll(writerMapper.selectWriterNamePrefix(prefix));
            return fallback.size() > 8 ? fallback.subList(0, 8) : fallback;
        }
    }

    /** 词库懒装载: 去重标题+诗人名, score恒0; 24h过期自愈(标题库变更后自动重建) */
    private void loadSuggestDict() {
        List<String> words = new ArrayList<>(potryMapper.GetAllTitles());
        words.addAll(writerMapper.getAllWriterNames());
        Set<org.springframework.data.redis.core.ZSetOperations.TypedTuple<String>> tuples = new HashSet<>();
        for (String w : words) {
            if (w != null && !w.isBlank()) {
                tuples.add(new org.springframework.data.redis.core.DefaultTypedTuple<>(w, 0.0));
            }
        }
        stringRedisTemplate.opsForZSet().add(SUGGEST_ZSET, tuples);
        stringRedisTemplate.expire(SUGGEST_ZSET, 24, java.util.concurrent.TimeUnit.HOURS);
        log.info("搜索补全词库已装载: {} 词", tuples.size());
    }

    @Override
    public List<Map<String, Object>> hotSearch() {
        try {
            Set<org.springframework.data.redis.core.ZSetOperations.TypedTuple<String>> set =
                    stringRedisTemplate.opsForZSet().reverseRangeWithScores(HOT_ZSET, 0, 9);
            if (set == null) {
                return Collections.emptyList();
            }
            List<Map<String, Object>> list = new ArrayList<>();
            for (var t : set) {
                Map<String, Object> m = new java.util.LinkedHashMap<>();
                m.put("kw", t.getValue());
                m.put("score", t.getScore() == null ? 0 : t.getScore().intValue());
                list.add(m);
            }
            return list;
        } catch (Exception e) {
            log.warn("热搜榜读取异常: {}", e.getMessage());
            return Collections.emptyList();
        }
    }

    /**
     * 热搜计数: 同用户同词60s去重(防连点/脚本刷榜), ZSet计数+24h滚动过期(滚动热搜),
     * removeRange只保留top1000防无限膨胀; 全链路try-catch,热搜故障不影响搜索主流程
     */
    private void recordHotSearch(String kw) {
        if (kw == null || kw.isBlank()) {
            return;
        }
        try {
            Long userId = BaseContext.getCurrentId();
            String guard = "poetry:hotsearch:u:" + userId + ":" + kw.trim().hashCode();
            Boolean first = stringRedisTemplate.opsForValue().setIfAbsent(guard, "1", 60, java.util.concurrent.TimeUnit.SECONDS);
            if (Boolean.TRUE.equals(first)) {
                stringRedisTemplate.opsForZSet().incrementScore(HOT_ZSET, kw.trim(), 1);
                stringRedisTemplate.expire(HOT_ZSET, 24, java.util.concurrent.TimeUnit.HOURS);
                stringRedisTemplate.opsForZSet().removeRange(HOT_ZSET, 1000, -1);
            }
        } catch (Exception e) {
            log.warn("热搜计数失败(不影响搜索): {}", e.getMessage());
        }
    }

}
