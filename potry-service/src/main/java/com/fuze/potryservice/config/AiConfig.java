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

      @Bean
    ChatClient  queryClient(ChatClient.Builder builder) {
        return builder.defaultSystem("我下面会给你传入一首古诗，将里面的生僻字和易错字给我提取出来,返回给我的数据只要有这些字，其他的都不需要，而且最少需要5个字，并且还要按照古诗的顺序依次排列")
                .build();
    }


}