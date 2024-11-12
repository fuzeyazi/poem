package com.fuze.utils;

import com.alibaba.fastjson.JSON;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.util.concurrent.TimeUnit;

@Slf4j
@Component
//redis工具类
public class RedisUtil {
  private StringRedisTemplate stringRedisTemplate;
  public RedisUtil (StringRedisTemplate stringRedisTemplate){
      this.stringRedisTemplate=stringRedisTemplate;
  }
    private void setRedisUtil(Object object,int time,String key,TimeUnit timeUnit) {
        String json= JSON.toJSONString(object);
        //timeUnit是时间单位
        stringRedisTemplate.opsForValue().set(key,json,time, timeUnit);
    }
}
