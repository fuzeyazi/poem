package com.fuze.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class RedisData {
    // 逻辑过期时间
    private LocalDateTime expireTime;
    // 缓存实际的内容
    private Object data;
}
