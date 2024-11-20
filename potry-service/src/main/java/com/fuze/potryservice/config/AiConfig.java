package com.fuze.potryservice.config;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
class AiConfig {

    @Bean
    ChatClient chatClient(ChatClient.Builder builder) {
        return builder.defaultSystem("我希望你以古代诗人王维的身份与我对话。")
                .build();
    }
    @Bean
    ChatClient chatClient2(ChatClient.Builder builder) {
        return builder.defaultSystem("我希望你以古代诗人周敦颐的身份与我对话。")
                .build();
    }
    @Bean
    ChatClient chatClient3(ChatClient.Builder builder) {
        return builder.defaultSystem("我希望你以古代诗人李清照的身份与我对话")
                .build();
    }
    @Bean
    ChatClient chatClient4(ChatClient.Builder builder) {
        return builder.defaultSystem("我希望你以古代诗人李白的身份与我对话")
                .build();
    }
    @Bean
    ChatClient chatClient5(ChatClient.Builder builder) {
        return builder.defaultSystem("我希望你以古代诗人杜甫的身份与我对话")
                .build();
    }
    @Bean
    ChatClient chatClient6(ChatClient.Builder builder) {
        return builder.defaultSystem("我希望你以古代诗人白居易的身份与我对话")
                .build();
    }
    @Bean
    ChatClient chatClient7(ChatClient.Builder builder) {
        return builder.defaultSystem("我希望你以古代诗人苏轼的身份与我对话")
                .build();
    }
    @Bean
    ChatClient chatClient8(ChatClient.Builder builder) {
        return builder.defaultSystem("我希望你以古代诗人陶渊明的身份与我对话")
                .build();
    }
      @Bean
    ChatClient  queryClient(ChatClient.Builder builder) {
        return builder.defaultSystem("我下面会给你传入一首古诗，将里面的生僻字和易错字给我提取出来,返回给我的数据只要有这些字，其他的都不需要，而且最少需要5个字，并且还要按照古诗的顺序依次排列")
                .build();
    }
    @Bean
    ChatClient  zuojia(ChatClient.Builder builder) {
        return builder.defaultSystem("下面我会给你传入一首诗句，你现在是一个知识渊博的老师，需要根据我给你发的请求来给我反馈。")
                .build();
    }
    @Bean
    ChatClient  gushitecher(ChatClient.Builder builder) {
        return builder.defaultSystem("下面我会给你个图片，你现在是一个知识渊博的古诗老师，能根据任何图片写出一首诗出来，要符合我给你的体裁a")
                .build();
    }
}