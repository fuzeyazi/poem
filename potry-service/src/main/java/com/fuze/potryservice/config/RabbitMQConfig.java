package com.fuze.potryservice.config;

import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.DirectExchange;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.amqp.rabbit.config.SimpleRabbitListenerContainerFactory;
import org.springframework.amqp.rabbit.config.RetryInterceptorBuilder;
import org.springframework.amqp.rabbit.connection.CachingConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.rabbit.retry.RejectAndDontRequeueRecoverer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * RabbitMQ 可靠性配置（2026-10-25 可靠消息闭环）：
 * 1. 生产者侧：publisher confirm/return 开启，NACK 或未路由到队列时 error 告警；
 * 2. 消费者侧：容器默认 requeue=true —— 毒消息会无限循环重投（实测 15s 打出 40 万行日志），
 *    改为本地重试 3 次(1s/2s/4s 退避) + 耗尽后 reject 且不 requeue → 经 DLX 进死信队列；
 * 3. 死信拓扑：post.dlx → post.notify.dead.queue，死信消费者记录告警+计数。
 * 业务队列 post.notify.queue 的死信参数声明见 PostNotifyListener 的 @Queue arguments。
 */
@Slf4j
@Configuration
public class RabbitMQConfig {

    public static final String POST_EXCHANGE = "post.exchange";
    public static final String POST_ROUTING_KEY = "post.created";
    public static final String POST_DLX = "post.dlx";
    public static final String POST_DEAD_ROUTING_KEY = "post.created.dead";
    public static final String POST_DEAD_QUEUE = "post.notify.dead.queue";

    @Bean
    public CachingConnectionFactory connectionFactory(
            @Value("${spring.rabbitmq.username:fuze}") String mqUsername,
            @Value("${spring.rabbitmq.password:}") String mqPassword) {
        CachingConnectionFactory connectionFactory = new CachingConnectionFactory();
        connectionFactory.setHost("localhost");
        connectionFactory.setPort(5672);
        connectionFactory.setVirtualHost("/");
        connectionFactory.setUsername(mqUsername);
        connectionFactory.setPassword(mqPassword);
        connectionFactory.setPublisherConfirmType(CachingConnectionFactory.ConfirmType.CORRELATED);
        connectionFactory.setPublisherReturns(true);
        return connectionFactory;
    }

    @Bean
    public RabbitTemplate rabbitTemplate(CachingConnectionFactory connectionFactory) {
        RabbitTemplate rabbitTemplate = new RabbitTemplate(connectionFactory);
        rabbitTemplate.setMandatory(true);
        // broker 确认 NACK(消息可能未落盘) —— 告警
        rabbitTemplate.setConfirmCallback((correlationData, ack, cause) -> {
            if (!ack) {
                log.error("MQ publisher confirm NACK: {} cause={}", correlationData, cause);
            }
        });
        // mandatory=true 且消息未路由到任何队列 —— 告警(消息已丢)
        rabbitTemplate.setReturnsCallback(returned -> log.error(
                "MQ消息未路由到队列: exchange={} routingKey={} replyText={} body={}",
                returned.getExchange(), returned.getRoutingKey(), returned.getReplyText(),
                new String(returned.getMessage().getBody())));
        return rabbitTemplate;
    }

    /**
     * 监听容器: 本地重试替代默认的 requeue 循环。
     * defaultRequeueRejected=false + RejectAndDontRequeueRecoverer:
     * 重试耗尽后 basic.reject → 队列声明的 x-dead-letter-exchange 接住 → 死信队列。
     */
    @Bean
    public SimpleRabbitListenerContainerFactory rabbitListenerContainerFactory(
            CachingConnectionFactory connectionFactory) {
        SimpleRabbitListenerContainerFactory factory = new SimpleRabbitListenerContainerFactory();
        factory.setConnectionFactory(connectionFactory);
        factory.setDefaultRequeueRejected(false);
        factory.setAdviceChain(RetryInterceptorBuilder.stateless()
                .maxAttempts(3)
                .backOffOptions(1000, 2.0, 4000)
                .recoverer(new RejectAndDontRequeueRecoverer())
                .build());
        return factory;
    }

    // ---------- 死信拓扑 ----------
    @Bean
    public DirectExchange postDlx() {
        return new DirectExchange(POST_DLX, true, false);
    }

    @Bean
    public Queue postDeadQueue() {
        return QueueBuilder.durable(POST_DEAD_QUEUE).build();
    }

    @Bean
    public Binding postDeadBinding() {
        return BindingBuilder.bind(postDeadQueue()).to(postDlx()).with(POST_DEAD_ROUTING_KEY);
    }

    // ---------- 以下为历史遗留(反馈链路, 见台账 backlog#4) ----------
    @Bean
    public Queue kkkQueue() {
        return new Queue("kkk", true);
    }

    @Bean
    public DirectExchange myExchange() {
        return new DirectExchange("myExchange", true, false);
    }

    @Bean
    public Binding kkkBinding(Queue kkkQueue) {
        return BindingBuilder.bind(kkkQueue).to(new org.springframework.amqp.core.TopicExchange("amq.topic")).with("kkk");
    }
}
