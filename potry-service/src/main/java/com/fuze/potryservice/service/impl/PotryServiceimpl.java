package com.fuze.potryservice.service.impl;

import cn.hutool.core.util.BooleanUtil;
import cn.hutool.core.util.StrUtil;
import com.alibaba.fastjson.JSON;
import com.fuze.entity.Poem;
import com.fuze.entity.Writer;
import com.fuze.entity.WriterEndVo;
import com.fuze.potryservice.mapper.PotryMapper;
import com.fuze.potryservice.service.PotryService;
import com.fuze.result.PageResult;
import com.fuze.vo.*;
import com.github.pagehelper.Page;
import com.github.pagehelper.PageHelper;
import com.github.pagehelper.PageInfo;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.concurrent.TimeUnit;
@Slf4j
@Service
public class PotryServiceimpl implements PotryService {
    @Autowired
    private PotryMapper potryMapper;
    @Autowired
    private StringRedisTemplate stringRedisTemplate;
    @Override
    public Integer getcount() {
       return potryMapper.getcount();
    }

    @Override
    public List<String> GetAllPoemName() {
        return potryMapper.GetAllPoemName();
    }


    @Override
    public Poem GetContentById(Integer id) {
        Poem poem = potryMapper.GetContentById(id);
        if (poem != null) {
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

        return poem;
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
    public PageResult GetPoemPage(Integer pageNum, Integer pageSize) {
        PageHelper.startPage(pageNum, pageSize);
        Page<PoemDataVo> page = potryMapper.GetPoemvoByPage1();
        long total = page.getTotal();
        List<PoemDataVo> records = page.getResult();
        return new PageResult(total, records);
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
        Poem poem=potryMapper.GetContentById(id);
        if(poem.getRemarks()==null|| poem.getRemarks().isEmpty()){
            poem.setRemarks("暂时没有收录");
        }
        if(poem.getTranslation()==null|| poem.getTranslation().isEmpty()){
            poem.setTranslation("暂时没有收录");
        }
        if(poem.getShangxi()==null|| poem.getShangxi().isEmpty()){
            poem.setShangxi("暂时没有收录");
        }
        return Arrays.asList(poem);
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
    public String getcountbyid(int id) {
        return potryMapper.getcountbyid(id);
    }

    @Override
    public void update(Integer userid,Integer poemid) {
        potryMapper.update(userid,poemid);
    }


    @Override
    public List<PoemDataVo> GetPoemDataVoByWriter(String name) {
        return potryMapper.GetPoemData(name);
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
        Boolean aBoolean = stringRedisTemplate.opsForValue().setIfAbsent(key, "1", 10, TimeUnit.SECONDS);
        return BooleanUtil.isTrue(aBoolean);
    }
    private void unLock(String key){
        stringRedisTemplate.delete(key);
    }

    @Override
    public WriterEndVo GetPoemWriter(int id) throws InterruptedException {
       //从redis查询诗人详细
      String poemjson=stringRedisTemplate.opsForValue().get("poem:writer:"+id);
      //判断是否存在
        if(StrUtil.isNotBlank(poemjson)){
            if (poemjson != null &&poemjson.equals("null")) {
                log.info("防止击穿");
                return null;
            }
            log.info("从redis查询诗人详细数据");
            //如果存在,将json反序列化成对象返回
            return JSON.parseObject(poemjson,WriterEndVo.class);
        }else{
            //缓存穿透
            String lock="lock:poem:writer:"+id;
            //1,获取互斥锁
            boolean trylock = trylock(lock);
            if(trylock){
                //2,如果获取锁成功，应该检查redis中是否有数据
                log.info("缓存穿透");
                String poemjson1=stringRedisTemplate.opsForValue().get("poem:writer:"+id);

                 //3,如果redis中存在数据，直接返回
                if(poemjson1!=null){
                    log.info("二次验证");
                    return JSON.parseObject(poemjson1,WriterEndVo.class);
                }
                //4，如果redis中不存在数据，则从数据库中查询数据

                List<WriterEndVo> writerEndVo1=potryMapper.GetPoemWriter1(id);
                //5如果数据库中不存在数据，则将null写入redis,做防止击穿
                if(writerEndVo1.isEmpty()){
                    log.info("返回一个空对象");
                    stringRedisTemplate.opsForValue().set("poem:writer:"+id,"null",1,TimeUnit.MINUTES);
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
                stringRedisTemplate.opsForValue().set("poem:writer:"+id,JSON.toJSONString(writerEndVo),30,TimeUnit.MINUTES);
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
