package com.fuze.potryservice;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.context.annotation.EnableAspectJAutoProxy;
import org.springframework.scheduling.annotation.EnableScheduling;

//@EnableWebSocketMessageBroker
@EnableCaching
@EnableScheduling
@EnableAspectJAutoProxy
@MapperScan("com.fuze.potryservice.mapper")
@SpringBootApplication(scanBasePackages = {"com.fuze"})
public class PotryServiceApplication {
    public static void main(String[] args) {
        var c = SpringApplication.run(PotryServiceApplication.class, args);
        System.out.println();
        System.setProperty("https.protocols", "TLSv1.2");
    }
}
