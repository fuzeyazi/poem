package com.fuze.potryservice.config.OPTIONS;

import jakarta.annotation.Resource;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.model.Media;
import org.springframework.ai.openai.OpenAiChatModel;
import org.springframework.ai.openai.OpenAiChatOptions;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;

import java.util.List;

@RestController
public class Chat {
    @Resource
    private OpenAiChatModel openAiChatModel;

    @RequestMapping("/aiaiaai")
    public Object chat(@RequestParam(value = "message") String message) {
        //OpenAiChatOptions 设置模型参数，with许多参数
        Prompt prompt = new Prompt("你好", OpenAiChatOptions.builder().withTemperature(0.4).build());
        ChatResponse chatResponse = openAiChatModel.call(prompt);
        return chatResponse.getResult().getOutput().getContent();
    }

    //流式
    @RequestMapping("/aiaiaaiddddddd")
    public Flux<String>  chat2(@RequestParam(value = "message") String message) {
        //OpenAiChatOptions 设置模型参数，with许多参数
        Prompt prompt = new Prompt("你好", OpenAiChatOptions.builder().withTemperature(0.4).build());
        Flux<ChatResponse> chatResponse = openAiChatModel.stream(prompt);
       return chatResponse.map(chatResponse1 -> chatResponse1.getResult().getOutput().getContent());
    }

    ;
}
 //多模态api----图生文
// @RequestMapping("/aiaiaaiddddddd2")
// public  Object chat3(@RequestParam(value = "message") String message,String url){
//     UserMessage userMessage=new UserMessage(message, List.of(MediaType)));
//}
//
//}
