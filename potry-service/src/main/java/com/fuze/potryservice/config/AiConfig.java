package com.fuze.potryservice.config;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
class AiConfig {

    @Bean
    ChatClient chatClient(ChatClient.Builder builder) {
        return builder.defaultSystem("我希望你以古代诗人李白的身份与我对话。")
                .build();
    }
    @Bean
    ChatClient chatClient2(ChatClient.Builder builder) {
        return builder.defaultSystem("我希望你以古代诗人白居易的身份与我对话。")
                .build();
    }
    @Bean
    ChatClient chatClient3(ChatClient.Builder builder) {
        return builder.defaultSystem("我希望你以古代诗人杜甫的身份与我对话。")
                .build();
    }



}