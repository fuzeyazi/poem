package com.fuze.response;

import com.alibaba.fastjson.JSONArray;
import lombok.Data;
import org.springframework.context.annotation.Lazy;

/**
 * Created with IntelliJ IDEA
 *
 * @author zhwang40
 * @date：2024/3/21
 * @time：15:12
 * @descripion:
 */
@Data
@Lazy
public class AgentCharacter {
    /**
     * 应用Id
     */
    private String appId;

    /**
     * 玩家账号
     */
    private String playerId;

    /**
     * 人格Id
     */
    private String agentId;

    /**
     * 人格名称
     */
    private String agentName;

    /**
     * 人格类型
     */
    private String agentType;

    /**
     * 人格描述
     */
    private String description;

    /**
     * 性格描述
     */
    private JSONArray personality;

    /**
     * 语言风格
     */
    private JSONArray languageStyle;

    /**
     * 社会身份
     */
    private String identity;

    /**
     * 爱好
     */
    private String hobby;

    /**
     * 头像地址
     */
    private String imageUrl;

    /**
     * 发音人
     */
    private String speaker;

    /**
     * 对话场景
     */
    private String openingIntroduction;
}
