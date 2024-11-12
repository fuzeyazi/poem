package com.fuze.potryservice.controller.user;

import com.aliyun.oss.OSS;
import com.aliyun.oss.OSSClientBuilder;
import com.fuze.context.BaseContext;
import com.fuze.potryservice.service.PotryService;
import com.fuze.utils.AliOssUtil;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import org.springframework.ai.audio.transcription.AudioTranscriptionPrompt;
import org.springframework.ai.audio.transcription.AudioTranscriptionResponse;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.MessageChatMemoryAdvisor;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.memory.InMemoryChatMemory;
import org.springframework.ai.image.ImagePrompt;
import org.springframework.ai.image.ImageResponse;
import org.springframework.ai.openai.*;
import org.springframework.ai.openai.api.OpenAiAudioApi;
import org.springframework.ai.openai.audio.speech.SpeechPrompt;
import org.springframework.ai.openai.audio.speech.SpeechResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;

import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.Random;
import java.util.UUID;

@RestController
@RequestMapping("/ai")
@Api(tags ="除了ai绘画，本接口是终结ai，其他ai默认无")
public class AiController {
    @Autowired
    private AliOssUtil aliOssUtil;

    @Autowired
    private ChatClient chatClient;
    @Autowired
    private ChatClient chatClient2;
    @Autowired
    private ChatClient chatClient3;
    @Autowired
    private OpenAiImageModel openaiImageModel;
    @Autowired
    private PotryService potryService;

    @Autowired
    private OpenAiAudioSpeechModel openAiAudioSpeechModel;

    private final ChatMemory chatMemory = new InMemoryChatMemory();
    @ApiOperation("用户进行ai对话，通过前端返回的id值来决定和哪个对话，")
    @GetMapping(value = "/chat",produces = "text/html;charset=UTF-8")
    //传入选择角色的id和内容
    public Flux<String> chat(@RequestParam Integer id, @RequestParam(value = "message") String message) {

        if (id == 1) {
            return this.chatClient.prompt()
                    .user(message)
                    .advisors(new MessageChatMemoryAdvisor(chatMemory, BaseContext.getCurrentId().toString(), 10))
                    .stream()
                    .content();
        } else if (id == 2){
            return this.chatClient2.prompt()
                    .user(message)
                    .advisors(new MessageChatMemoryAdvisor(chatMemory, BaseContext.getCurrentId().toString(), 10))
                    .stream()
                    .content();
        }else{
            return this.chatClient3.prompt()
                    .user(message)
                    .advisors(new MessageChatMemoryAdvisor(chatMemory, BaseContext.getCurrentId().toString(), 10))
                    .stream()
                    .content();
        }
    }
    @ApiOperation("ai语言朗诵古诗--根据传回来的id值决定什么诗句")
    @GetMapping(value = "/audio")
    public String audio(@RequestParam Integer id) throws IOException {
        String message=potryService.GetContentById(id).getContent();
        //文生语音的配置
        OpenAiAudioSpeechOptions speechOptions = OpenAiAudioSpeechOptions.builder()
                .withModel("tts-1")
                // 声色配置
                .withVoice(OpenAiAudioApi.SpeechRequest.Voice.ONYX)
                // 响应格式
                .withResponseFormat(OpenAiAudioApi.SpeechRequest.AudioResponseFormat.MP3)
                // 语速配置
                .withSpeed(0.8f)
                .build();
        SpeechPrompt speechPrompt = new SpeechPrompt(message, speechOptions);
            SpeechResponse response = openAiAudioSpeechModel.call(speechPrompt);
            //oss上传文件
            String ss = UUID.randomUUID().toString();
            String url = aliOssUtil.upload(response.getResult().getOutput(), ss+".mp3");
            return url;
        //上传到阿里oss


        //TODO 文件存放于本地 项目根目录下
//        FileOutputStream fos = new FileOutputStream( System.getProperty("user.dir")+"/"+UUID.randomUUID()+"ai.mp3");
//        fos.write(response.getResult().getOutput());
//        fos.close();


    }







}
