package com.fuze.potryservice.config;

import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.connection.CachingConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {

    // 配置连接工厂
    @Bean
    public CachingConnectionFactory connectionFactory() {
        CachingConnectionFactory connectionFactory = new CachingConnectionFactory();
        connectionFactory.setHost("localhost");
        connectionFactory.setPort(5672);
        connectionFactory.setVirtualHost("/");
        connectionFactory.setUsername("fuze");
        connectionFactory.setPassword("123456");
        return connectionFactory;
    }

    // 配置RabbitTemplate
    @Bean
    public RabbitTemplate rabbitTemplate(CachingConnectionFactory connectionFactory) {
        RabbitTemplate rabbitTemplate = new RabbitTemplate(connectionFactory);
        return rabbitTemplate;
    }

    // 配置队列
    @Bean
    public Queue kkkQueue() {
        return new Queue("kkk", true);
    }

    // 配置交换器
    @Bean
    public DirectExchange myExchange() {
        return new DirectExchange("myExchange", true, false);
    }

    // 配置绑定
    @Bean
    public Binding kkkBinding(Queue kkkQueue) {
        return BindingBuilder.bind(kkkQueue).to(new TopicExchange("amq.topic")).with("kkk");
    }
}
