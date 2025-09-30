package com.fuze.potryservice.service.impl;

import com.alibaba.fastjson.JSON;
import com.fuze.dto.PoemBlogDtoPlus;
import com.fuze.potryservice.mapper.PoemLunTanMapper;
import org.mybatis.logging.Logger;
import org.mybatis.logging.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import com.fasterxml.jackson.databind.ObjectMapper;
@Service
public class AsyncService {
    private static final Logger logger = LoggerFactory.getLogger(AsyncService.class);
    @Autowired
    private StringRedisTemplate stringRedisTemplate;
    @Autowired
    private PoemLunTanMapper poemLunTanMapper;
    @Autowired
    @Qualifier("forumThreadPool")
    private Executor threadPool;
    public void asyncNotifyFans(PoemBlogDtoPlus poemBlogDtoPlus,Integer id){
      CompletableFuture<Void> future = CompletableFuture.runAsync(() -> {
          List<Integer> userIds = poemLunTanMapper.getuseridbylistid(id);
          try{
              long startTime = System.currentTimeMillis();
              for (Integer userId : userIds) {
                  String key = "fan:" + userId;
                  stringRedisTemplate.opsForZSet().add(
                          key,
                          String.valueOf(poemBlogDtoPlus.getBolgid()),
                          System.currentTimeMillis()
                  );
              }
              ValueOperations<String, String> ops = stringRedisTemplate.opsForValue();
              String poemBlogDtoPlusjson= JSON.toJSONString(poemBlogDtoPlus);
              String key = "blog:" + poemBlogDtoPlus.getBolgid();
             ops.set(key, poemBlogDtoPlusjson, 3600);
              long duration = System.currentTimeMillis() - startTime;
              System.out.println("粉丝通知任务完成! 处理数量: {}, 耗时: {}ms"+userIds.size()+duration);
          }catch(Exception e){
              System.out.println("这个人没有粉丝");
          }
      }, threadPool);
        future.whenComplete((result, throwable) -> {
            if (throwable != null) {
                System.out.println("任务执行异常"+throwable);

            } else {
                System.out.println("异步任务已成功完成");
            }
        });
    }
}
