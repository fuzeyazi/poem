package com.fuze.potryservice.task;

import com.fuze.potryservice.mapper.UserMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * 复习提醒推送(2026-10-25): 每日9点扫描艾宾浩斯SRS到期用户——
 * 在线用户经 STOMP /topic/review.{userId} 实时推送,提醒历史落 Redis ZSet(7条);
 * 每日分布式锁(SETNX)防止多实例重复跑批,用户级当日防重防止重复打扰。
 * 管理端 POST /admin/remind/trigger 可手动触发(演示/补偿用)。
 */
@Slf4j
@Component
public class ReviewRemindTask {

    private static final DateTimeFormatter DATE = DateTimeFormatter.ofPattern("yyyyMMdd");

    @Autowired
    private UserMapper userMapper;
    @Autowired
    private StringRedisTemplate stringRedisTemplate;
    @Autowired
    private SimpMessagingTemplate simpMessagingTemplate;

    /** 每日9:00跑批 */
    @Scheduled(cron = "0 0 9 * * ?")
    public void schedule() {
        trigger(false);
    }

    /**
     * @param force true=管理端手动触发(跳过当日批次锁,仍受用户级防重约束)
     * @return 执行结果描述
     */
    public String trigger(boolean force) {
        String date = LocalDate.now().format(DATE);
        // 批次锁: 多实例部署时当日只允许一个实例跑批(单机无实际作用,语义防重)
        if (!force) {
            Boolean got = stringRedisTemplate.opsForValue()
                    .setIfAbsent("remind:lock:" + date, "1", 25, TimeUnit.HOURS);
            if (!Boolean.TRUE.equals(got)) {
                return "今日批次已执行过,跳过";
            }
        }
        List<Map<String, Object>> due = userMapper.GetDueReviewUsers();
        int pushed = 0;
        for (Map<String, Object> row : due) {
            Long userId = ((Number) row.get("userId")).longValue();
            int cnt = ((Number) row.get("cnt")).intValue();
            // 用户级当日防重: 定时+手动触发叠加时同用户当日只提醒一次
            Boolean first = stringRedisTemplate.opsForValue()
                    .setIfAbsent("remind:sent:" + date + ":" + userId, "1", 25, TimeUnit.HOURS);
            if (!Boolean.TRUE.equals(first)) {
                continue;
            }
            try {
                Map<String, Object> msg = new HashMap<>();
                msg.put("type", "review_remind");
                msg.put("count", cnt);
                msg.put("date", LocalDate.now().toString());
                simpMessagingTemplate.convertAndSend("/topic/review." + userId, msg);
                // 提醒历史(最近7条): ZSet score=时间戳
                String logKey = "remind:log:" + userId;
                stringRedisTemplate.opsForZSet().add(logKey,
                        LocalDate.now() + ":" + cnt, System.currentTimeMillis());
                stringRedisTemplate.opsForZSet().removeRange(logKey, 0, -8);
                pushed++;
            } catch (Exception e) {
                log.warn("复习提醒推送失败 userId={}: {}", userId, e.getMessage());
            }
        }
        log.info("复习提醒跑批完成: 到期用户{}人, 推送{}人", due.size(), pushed);
        return "到期用户" + due.size() + "人, 推送" + pushed + "人";
    }
}
