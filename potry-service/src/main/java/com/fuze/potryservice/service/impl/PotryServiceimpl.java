package com.fuze.potryservice.service.impl;

import cn.hutool.core.util.BooleanUtil;
import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONUtil;
import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.JSONObject;
import com.fuze.context.BaseContext;
import com.fuze.entity.Poem;
import com.fuze.entity.Writer;
import com.fuze.entity.WriterEndVo;
import com.fuze.potryservice.mapper.PotryMapper;
import com.fuze.potryservice.service.PotryService;

import com.fuze.response.RedisData;
import com.fuze.result.PageResult;
import com.fuze.vo.*;
import com.github.pagehelper.Page;
import com.github.pagehelper.PageHelper;
import com.github.pagehelper.PageInfo;
import lombok.extern.slf4j.Slf4j;
import org.redisson.Redisson;
import org.redisson.api.RBucket;
import org.redisson.api.RedissonClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
@Slf4j
@Service
public class PotryServiceimpl implements PotryService {
    @Autowired
    private PotryMapper potryMapper;
    @Autowired
    private StringRedisTemplate stringRedisTemplate;
    @Autowired
    private RedissonClient redissonClient;
    @Override
    public Integer getcount() {
       return potryMapper.getcount();
    }

    @Override
    public List<String> GetAllPoemName() {
        return potryMapper.GetAllPoemName();
    }

    private final ExecutorService executorService = Executors.newSingleThreadExecutor();
    @Override
    public Poem GetContentById(Integer id) {
        String poemkey = "poem:" + "context:" + id;
        String json = stringRedisTemplate.opsForValue().get(poemkey);
        if (json == null) {
            return loadAndCachePoem(id, poemkey);
        }
        RedisData redispoem = JSONObject.parseObject(json, RedisData.class);
        LocalDateTime expireTime = redispoem.getExpireTime();
        if (expireTime.isAfter(LocalDateTime.now())) {
            return JSONObject.parseObject(redispoem.getData().toString(), Poem.class);
        } else {
            String lockkey = "lock:poem:" + id;
            if (trylock(lockkey)) {
                executorService.submit(() -> {
                    try {
                        Poem poem = loadAndCachePoem(id, poemkey);
                    } catch (Exception e) {
                        e.printStackTrace();
                    } finally {
                        unLock(lockkey);
                    }
                });
            }
            return JSONObject.parseObject(json, Poem.class);
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
    public List<String> GetAllDynasty() {
        return potryMapper.Getdynasty();
    }

    @Override
    public List<DynatryPoemResultVO> GetDynastyPoemResulVo() {
        return potryMapper.GetDynastyPoemResulVo();
    }

    @Override
    public List<PoemDataVo> GetPoemDataVoByDynasty(String dynasty) {
        return potryMapper.GetPoemDataVoByDynasty(dynasty);
    }

    @Override
    public List<PoemDataVo> GetPoemDateRondom() {
        return potryMapper.GetPoemDateRondom();

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
    public PageResult GetwriterBydynasty1() {
        return potryMapper.GetwriterBydynasty1();
    }

    @Override
    public List<Writer> GetRondWriter() {
        return potryMapper.GetRondWriter();
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

                // 未过期，返回数据
                return Collections.singletonList(JSONObject.parseObject(json, Poem.class));
            }else{
                String lockKey = "lock:shop:" + id;
                boolean lock = trylock(lockKey);
                if (lock) {
                    executorService.submit(() -> {
                        Poem poem=potryMapper.GetContentById(id);
                        redisData.setData(poem);
                        redisData.setExpireTime(LocalDateTime.now().plusMinutes(30));
                        stringRedisTemplate.opsForValue().set(pomekey, JSONUtil.toJsonStr(redisData));
                        unLock(lockKey);
                    });
                }
                return Collections.singletonList(JSONObject.parseObject(json, Poem.class));
            }

        }
    }

    @Override
    public PageResult GetPoembyTitle(Integer pageNum, Integer pageSize, String title) {
        PageHelper.startPage(pageNum, pageSize);
        Page<Poem> page=potryMapper.GetPoembyTitle(title);
        long total = page.getTotal();
        List<Poem> records = page.getResult();
        return new PageResult(total, records);
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
    @Override
    public PoemDataVo GetVeryGoodPoem() {
        return potryMapper.GetVeryGoodPoem();
    }
    private boolean trylock(String key){
        //使用setnx占坑，setIfAbsent
        Boolean aBoolean1 =stringRedisTemplate.opsForValue().setIfAbsent(key+"1", "1", 10, TimeUnit.SECONDS);
        String key1=key+"1";
        stringRedisTemplate.delete(key1);

        Boolean aBoolean = stringRedisTemplate.opsForValue().setIfAbsent(key, "1", 10, TimeUnit.SECONDS);
        return BooleanUtil.isTrue(aBoolean);
    }

    private void unLock(String key){
        stringRedisTemplate.delete(key);
    }
    @Override
    public WriterEndVo GetPoemWriter(int id) throws InterruptedException {
        RBucket<Object> bucket = redissonClient.getBucket("poem:writer:" + id);
        WriterEndVo poemjson= (WriterEndVo) bucket.get();
        //从redis查询诗人详细

      //判断是否存在
        if(poemjson!=null){
            if (poemjson.equals("null")) {
                log.info("防止击穿");
                return null;
            }
            log.info("从redis查询诗人详细数据");
            //如果存在,将json反序列化成对象返回
            return poemjson;
        }else{
            //缓存穿透
            String lock="lock:poem:writer:"+id;
            //1,获取互斥锁
            boolean trylock = trylock(lock);
            if(trylock){
                //2,如果获取锁成功，应该检查redis中是否有数据
                log.info("缓存穿透");

                WriterEndVo poemjson1= (WriterEndVo) bucket.get();
                 //3,如果redis中存在数据，直接返回
                if(poemjson1!=null){
                    log.info("二次验证");
                    return poemjson1;
                }
                //4，如果redis中不存在数据，则从数据库中查询数据
                List<WriterEndVo> writerEndVo1=potryMapper.GetPoemWriter1(id);
                //5如果数据库中不存在数据，则将null写入redis,做防止击穿
                if(writerEndVo1.isEmpty()){
                    log.info("返回一个空对象");
                    bucket.set("null",1,TimeUnit.MINUTES);
                    unLock(lock);
                    return null;
                }
                String dynasty=writerEndVo1.get(0).getDynasty();
                if(writerEndVo1.size()>1){
                    for(int i=1;i<writerEndVo1.size();i++){
                        dynasty=writerEndVo1.get(i).getDynasty()+','+dynasty;
                    }
                }
                writerEndVo1.get(0).setDynasty(dynasty);
                WriterEndVo writerEndVo=writerEndVo1.get(0);
                //如果缓存中没有数据，则在进行数据重建
                bucket.set(writerEndVo,30,TimeUnit.MINUTES);
                unLock(lock);
                return writerEndVo;
            }else{
                //不存在锁住，等待
                Thread.sleep(50);
                return GetPoemWriter(id);
            }
        }
    }
}
