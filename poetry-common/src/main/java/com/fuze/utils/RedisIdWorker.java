package com.fuze.utils;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;

@Component
public class RedisIdWorker {
    private static final int Count=32;
    @Autowired
    private StringRedisTemplate stringRedisTemplate;
    //生成全局id
    public long nextId(String keyprefix){
        LocalDateTime now = LocalDateTime.now();
        //生成时间戳
        LocalDateTime localDateTime = LocalDateTime.of(2024, 11, 16, 0, 0, 0);
       long time=localDateTime.toEpochSecond(ZoneOffset.UTC);
        long Millis = System.currentTimeMillis();
        long data=time-Millis;
        //序列号,使用了redis的自增功能,key后面拼接一个时间戳是因为怕
         //获取当天的时间
        String format = now.format(DateTimeFormatter.ofPattern("yyyy:MM:dd"));
        //自增长
        long count=stringRedisTemplate.opsForValue().increment("icr:"+keyprefix+":"+format);
        //将时间戳和序列号拼接起来，使用位运算,data 左移32位，然后使用| 运算，如果count是0,那么就返回data，否则就返回count；
        return data<<Count|count;
    }
}
