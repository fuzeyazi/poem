package com.fuze.potryservice;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Bean;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.StringRedisTemplate;

import java.time.LocalDateTime;


@SpringBootTest
class PotryServiceApplicationTests {
    @Autowired
    private StringRedisTemplate stringRedisTemplate;;
    @Test
    void contextLoads() {
        LocalDateTime localDateTime = LocalDateTime.of(2024, 11, 16, 0, 0, 0);
        System.out.println(localDateTime);
    }

}
