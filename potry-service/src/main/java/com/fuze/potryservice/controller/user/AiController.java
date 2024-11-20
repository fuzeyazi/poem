package com.fuze.potryservice.controller.user;

import com.fuze.context.BaseContext;
import com.fuze.dto.AiChatDto;
import com.fuze.potryservice.service.PotryService;
import com.fuze.result.Result;
import com.fuze.utils.AliOssUtil;
import com.fuze.potryservice.config.SseEmitterXIUGAI;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import jakarta.annotation.Resource;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.MessageChatMemoryAdvisor;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.memory.InMemoryChatMemory;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.model.Media;
import org.springframework.ai.openai.*;
import org.springframework.ai.openai.api.OpenAiApi;
import org.springframework.ai.openai.api.OpenAiAudioApi;
import org.springframework.ai.openai.audio.speech.SpeechPrompt;
import org.springframework.ai.openai.audio.speech.SpeechResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.ClassPathResource;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Retryable;
import org.springframework.util.Base64Utils;
import org.springframework.util.MimeTypeUtils;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import org.springframework.web.util.UriComponentsBuilder;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Sinks;

import java.io.*;
import java.lang.reflect.InvocationTargetException;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URISyntaxException;
import java.net.URL;
import java.nio.file.Files;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

@RestController
@RequestMapping("/ai")
@Api(tags ="除了ai绘画，本接口是终结ai，其他ai默认无")
public class AiController {
    @Autowired
    private AliOssUtil aliOssUtil;
    @Autowired
    private OpenAiChatModel chatModel;
    @Autowired
    public void ChatController(OpenAiChatModel chatModel) {
        this.chatModel = chatModel;
    }
   @Autowired
   private ChatClient gushitecher;
    @Autowired
    private ChatClient chatClient;
    @Autowired
    private ChatClient chatClient2;
    @Autowired
    private ChatClient chatClient3;
    @Autowired
    private ChatClient chatClient4;
    @Autowired
    private ChatClient chatClient5;
    @Autowired
    private ChatClient chatClient6;
    @Autowired
    private ChatClient chatClient7;
    @Autowired
    private ChatClient chatClient8;
    @Autowired
    private RestTemplate restTemplate;
    @Autowired
    private OpenAiImageModel openaiImageModel;
    @Autowired
    private PotryService potryService;
@Autowired
private ChatClient zuojia;
    @Autowired
    private StringRedisTemplate stringRedisTemplate;

    @Autowired
    private OpenAiAudioSpeechModel openAiAudioSpeechModel;

    private final ChatMemory chatMemory = new InMemoryChatMemory();

//    @ApiOperation("用户进行ai对话，通过前端返回的id值来决定和哪个对话，")
//    @PostMapping(value = "/chat")
//    //传入选择角色的id和内容
//    public Flux<String> chat(@RequestParam Integer id, @RequestParam(value = "message") String message) {
//        String userid = String.valueOf(BaseContext.getCurrentId());
//        ChatClient SchatClient;
//        if (id == 1) {
//            SchatClient = this.chatClient;
//        } else if (id == 2) {
//            SchatClient = this.chatClient2;
//        } else if(id==3) {
//            SchatClient = this.chatClient3;
//        }else if(id==10086){
//            SchatClient=this.zuojia;
//        }else{
//            SchatClient=this.chatClient;
//        }
//
//        return SchatClient.prompt()
//                .user(message)
//                .advisors(new MessageChatMemoryAdvisor(chatMemory, BaseContext.getCurrentId().toString(), 10))
//                .stream()//流式是用Stream()
//                .content();
////        woko = queryClient.prompt()
////                .user(context)
////                .advisors(new MessageChatMemoryAdvisor(chatMemory, BaseContext.getCurrentId().toString(), 10))
////                .call()//流式是用Stream()
////                .content();
//    }

    public final Map<String, SseEmitter> pool = new ConcurrentHashMap<>();

    @ApiOperation(value = "先强绑定")
    @GetMapping("/submita")
    private SseEmitter getSseEmitter() {
        String id = BaseContext.getCurrentId().toString();
        SseEmitter sseEmitter = pool.get(id);
        if (Objects.isNull(sseEmitter)) {
            sseEmitter = new SseEmitter(0L);
            sseEmitter.onCompletion(() -> pool.remove(id));
            sseEmitter.onTimeout(() -> pool.remove(id));
            pool.put(id, sseEmitter);
        }
        System.out.println("发送1");
        return sseEmitter;
    }
    private final Sinks.Many<String> sink = Sinks.many().multicast().onBackpressureBuffer();

    @ApiOperation("用户进行ai对话，通过前端返回的id值来决定和哪个对话，")
    @PostMapping(value = "/chat11")
    private Result<String> chat11(@RequestBody AiChatDto aiChatDto) throws IOException {
        String id = String.valueOf(BaseContext.getCurrentId());
        Integer idd = aiChatDto.getIdd();
        String message = aiChatDto.getMessage();
        SseEmitter sseEmitter = pool.get(id);
        if (Objects.isNull(sseEmitter)) {
            throw new RuntimeException("sseEmitter is null");
        }
        ChatClient SchatClient;
        if (idd == 1) {
            SchatClient = this.chatClient;
        } else if (idd == 2) {
            SchatClient = this.chatClient2;
        } else if(idd==3){
            SchatClient = this.chatClient3;
        }else if(idd==4){
            SchatClient = this.chatClient4;
        }else if(idd==5){
            SchatClient = this.chatClient5;
        }
        else if(idd==6){
            SchatClient = this.chatClient6;
        }
        else if(idd==7){
            SchatClient = this.chatClient7;
        }else if(idd==8){
            SchatClient = this.chatClient8;
        }else{
            SchatClient=this.zuojia;
        }
//        String zz=SchatClient.prompt().user(message)
//                    .advisors(new MessageChatMemoryAdvisor(chatMemory, BaseContext.getCurrentId().toString(), 10))
//                    .call()
//                    .content();
//        sseEmitter.send(zz);
        Flux.create(sink -> {
        SchatClient.prompt()
                .user(message)
                .advisors(new MessageChatMemoryAdvisor(chatMemory, BaseContext.getCurrentId().toString(), 10))
                .stream()
                .content()
                .doOnNext(content-> {
                    try {
                        sseEmitter.send(SseEmitter.
                                event()
                                .data(content)
                                .id(UUID.randomUUID().toString()));
                    } catch (IOException e) {
                        sseEmitter.completeWithError(e);
                        sink.error(e);
                    }
                })
                .doOnError(e -> {
                    sseEmitter.completeWithError(e);
                    sink.error(e);
                })
                .subscribe(); // 确保在这里订阅
    }).subscribe(); // 确保在这里订阅
        return Result.success("sb");
    }
    @ApiOperation("ai语言朗诵古诗--根据传回来的id值决定什么诗句")
    @GetMapping(value = "/audio")
    public String audio(@RequestParam Integer id) throws IOException {

        String isurl=stringRedisTemplate.opsForValue().get("yingpiurl:"+id);
        if(isurl==null) {
            String message = potryService.GetContentById(id).getContent();
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
            String url = aliOssUtil.upload(response.getResult().getOutput(), ss + ".mp3");
            stringRedisTemplate.opsForValue().set("yingpiurl:"+id,url);
            return url;
        }else{
            return isurl;
        }
        //上传到阿里oss
        //TODO 文件存放于本地 项目根目录下
//        FileOutputStream fos = new FileOutputStream( System.getProperty("user.dir")+"/"+UUID.randomUUID()+"ai.mp3");
//        fos.write(response.getResult().getOutput());
//        fos.close();
    }

    @ApiOperation("ai图生文")
    @PostMapping(value = "/picture")
    public  Result<Object> picture(@RequestParam String msg, @RequestParam String url) throws IOException, URISyntaxException, NoSuchMethodException, InvocationTargetException, IllegalAccessException {
        File localFile = downloadImageToLocal(url);
        SseEmitter emitter = new SseEmitter(60_000L); // 设置超时时间为60秒
        if (localFile == null || !localFile.exists()) {
            return Result.error("图片下载失败");
        }
        byte[] imageData = Files.readAllBytes(localFile.toPath());

//        byte[] imageData = new ClassPathResource("E:\\玩原神玩的组\\db735630-b8be-4e46-8ec9-eeb566705aa1.jpg").getContentAsByteArray();
        UserMessage userMessage = new UserMessage("现在我给你发送一个图片，给我生成一个古诗"+msg, List.of(new
                Media(MimeTypeUtils.IMAGE_PNG, imageData)));
        //调用chat模型
        Prompt prompt = new Prompt(userMessage);
        //调用chat模型
        ChatResponse chatResponse = chatModel.call(prompt);
        emitter.send(SseEmitter.event()
                .data(Result.success(chatResponse.getResult().getOutput().getContent()))
                .name("result"));
        emitter.complete();

        localFile.delete();
        return  Result.success(chatResponse.getResult().getOutput().getContent());
    }
    private File downloadImageToLocal(String urlString) throws IOException {

        URL url = new URL(urlString);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setRequestMethod("GET");
        connection.setConnectTimeout(5000);
        connection.setReadTimeout(5000);
        connection.connect();

        int responseCode = connection.getResponseCode();
        if (responseCode != 200) {
            throw new IOException("无法下载图片，HTTP 状态码: " + responseCode);
        }

        File tempFile = File.createTempFile("temp_image_", ".PNG");
        try (InputStream in = connection.getInputStream();
             FileOutputStream out = new FileOutputStream(tempFile)) {
            byte[] buffer = new byte[1024];
            int bytesRead;
            while ((bytesRead = in.read(buffer)) != -1) {
                out.write(buffer, 0, bytesRead);
            }
        }

        return tempFile;
    }

}

