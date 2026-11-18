package com.fuze.properties;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.stereotype.Component;
import org.springframework.stereotype.Repository;


@ConfigurationProperties(prefix = "sky.jwt")
@Data
@Component
public class JwtProperties {

    /**
     * 管理端员工生成jwt令牌相关配置
     */
    private String adminSecretKey;
    private long adminTtl;
    private String adminTokenName;

    /**
     * 用户端微信用户与pc端用户生成jwt令牌相关配置
     */
    private String userSecretKey;
    private long userTtl;
    private String userTokenName;

    /**
     * 密钥轮换过渡期: 验签主密钥失败后回退尝试的旧密钥列表(逗号分隔,默认空)。
     * 轮换流程: 换新主密钥重启 -> 旧token靠legacy继续验签 -> TTL自然过期后清空legacy
     */
    private String adminLegacySecretKeys = "";
    private String userLegacySecretKeys = "";



    // todo  pc端用户生成JWT令牌相关配置

}
