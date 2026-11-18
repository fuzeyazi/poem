package com.fuze.potryservice.mq;

import com.alibaba.fastjson.JSON;
import com.fuze.dto.PoemBlogDtoPlus;
import com.fuze.potryservice.mapper.PoemLunTanMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.Argument;
import org.springframework.amqp.rabbit.annotation.Exchange;
import org.springframework.amqp.rabbit.annotation.Queue;
import org.springframework.amqp.rabbit.annotation.QueueBinding;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * 发帖事件消费者(RabbitMQ):承担原线程池直推的粉丝通知,并新增在线实时推送。
 * 队列/交换机/绑定由注解声明式创建(post.exchange -> post.notify.queue, routingKey=post.created)
 */
@Slf4j
@Component
public class PostNotifyListener {

    @Autowired
    private PoemLunTanMapper poemLunTanMapper;
    @Autowired
    private StringRedisTemplate stringRedisTemplate;
    @Autowired
    private SimpMessagingTemplate simpMessagingTemplate;

    @RabbitListener(bindings = @QueueBinding(
            value = @Queue(value = "post.notify.queue", durable = "true", arguments = {
                    @Argument(name = "x-dead-letter-exchange", value = "post.dlx"),
                    @Argument(name = "x-dead-letter-routing-key", value = "post.created.dead")
            }),
            exchange = @Exchange(value = "post.exchange", type = "direct"),
            key = "post.created"))
    public void onPostCreated(String message,
                              @org.springframework.messaging.handler.annotation.Header(name = "traceId", required = false) String traceId) {
        long t0 = System.currentTimeMillis();
        if (traceId != null) {
            org.slf4j.MDC.put("traceId", traceId);   // 与发帖请求同traceId,日志可串联
        }
        try {
        PoemBlogDtoPlus post = JSON.parseObject(message, PoemBlogDtoPlus.class);
        // 消费幂等: redelivery/重复投递(重试跨重启、补偿重投)时跳过,防粉丝收件箱与STOMP重复触达
        try {
            Boolean first = stringRedisTemplate.opsForValue()
                    .setIfAbsent("post:notified:" + post.getBolgid(), "1", Duration.ofHours(24));
            if (!Boolean.TRUE.equals(first)) {
                log.info("重复消息幂等跳过: 帖子id={}", post.getBolgid());
                return;
            }
        } catch (Exception e) {
            log.warn("幂等键写入失败(Redis异常),放行继续消费(重复触达无害)", e);
        }
        //①粉丝收件箱(推模式feed):帖子id写进每个粉丝的ZSet,score=时间戳
        List<Integer> fans = poemLunTanMapper.getuseridbylistid(post.getUserid());
        for (Integer fanId : fans) {
            stringRedisTemplate.opsForZSet().add("fan:" + fanId,
                    String.valueOf(post.getBolgid()), System.currentTimeMillis());
        }
        //②帖子内容缓存1小时(收件箱点开详情时直接取)
        stringRedisTemplate.opsForValue().set("blog:" + post.getBolgid(), message, 3600, TimeUnit.SECONDS);
        //③WebSocket实时广播:在线用户即时收到新帖提醒(可扩展为按粉丝定向)
        Map<String, Object> notice = new HashMap<>();
        notice.put("type", "newpost");
        notice.put("bolgid", post.getBolgid());
        notice.put("title", post.getTitle());
        notice.put("userid", post.getUserid());
        simpMessagingTemplate.convertAndSend("/topic/newpost", notice);
        log.info("发帖通知消费完成: 帖子id={} 粉丝{}人 耗时{}ms",
                post.getBolgid(), fans.size(), System.currentTimeMillis() - t0);
        } finally {
            org.slf4j.MDC.remove("traceId");
        }
    }

    /**
     * 死信消费者: 消费重试3次(1s/2s/4s)耗尽仍失败的消息经 post.dlx 落到此处。
     * 生产要求是告警+人工介入; 此处记录error日志与Redis计数(mq:dead:count)。
     */
    @org.springframework.amqp.rabbit.annotation.RabbitListener(
            queues = com.fuze.potryservice.config.RabbitMQConfig.POST_DEAD_QUEUE)
    public void onDeadPostNotify(String message) {
        try {
            stringRedisTemplate.opsForValue().increment("mq:dead:count");
        } catch (Exception ignore) {
        }
        log.error("消息进入死信(重试3次耗尽,需人工介入): {}",
                message.substring(0, Math.min(200, message.length())));
    }
}
