package com.fuze.potryservice;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.web.socket.config.annotation.EnableWebSocketMessageBroker;

//@EnableWebSocketMessageBroker
@EnableCaching
@SpringBootApplication(scanBasePackages = {"com.fuze"})
public class PotryServiceApplication {

    public static void main(String[] args) {
        var c = SpringApplication.run(PotryServiceApplication.class, args);
        System.out.println();
    }
}