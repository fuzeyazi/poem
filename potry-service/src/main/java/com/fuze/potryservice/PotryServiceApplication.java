package com.fuze.potryservice;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cache.annotation.EnableCaching;

//@EnableWebSocketMessageBroker
@EnableCaching
@SpringBootApplication(scanBasePackages = {"com.fuze"})
public class PotryServiceApplication {
    public static void main(String[] args) {
        var c = SpringApplication.run(PotryServiceApplication.class, args);
        System.out.println();
        System.setProperty("https.protocols", "TLSv1.2");
    }
}
