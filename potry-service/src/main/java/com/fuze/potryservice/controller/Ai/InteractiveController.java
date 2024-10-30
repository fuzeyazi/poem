//package com.fuze.potryservice.controller.Ai;
//
//import cn.hutool.json.JSONUtil;
//import com.alibaba.fastjson.JSON;
//import com.alibaba.fastjson.JSONObject;
//import com.fuze.dto.InteractiveRequest;
//import com.fuze.dto.InteractiveResponse;
//import com.fuze.potryservice.service.UserService;
//import com.fuze.utils.AuthUtil;
//import io.swagger.annotations.Api;
//import okhttp3.*;
//import org.jetbrains.annotations.NotNull;
//import org.jetbrains.annotations.Nullable;
//import org.slf4j.Logger;
//import org.slf4j.LoggerFactory;
//import org.springframework.beans.factory.annotation.Autowired;
//import org.springframework.http.HttpStatus;
//import org.springframework.http.ResponseEntity;
//import org.springframework.web.bind.annotation.PostMapping;
//import org.springframework.web.bind.annotation.RequestParam;
//import org.springframework.web.bind.annotation.RestController;
//
//import java.util.ArrayList;
//import java.util.List;
//import java.util.UUID;
//@Api(tags ="AI")
//@RestController
//public class InteractiveController {
//
//    private static final Logger logger = LoggerFactory.getLogger(InteractiveController.class);
//
//    @Autowired
//    private UserService userService;
//
//    private static final String interactiveUrl = "wss://ai-character.xfyun.cn/api/open/interactivews/";
//    private static final String appId = "4b88e2d9";
//    private static final String secret = "NDJkYWVjOTk2ODg5N2ExMDIyMWJkNGNm";
////    @RequestParam("id") int id, @RequestParam String name, @RequestParam String texts
//    @PostMapping("/userInput")
//    public ResponseEntity<InteractiveResponse> userInput(){
//           int id=1;
//          String   name = "李白";
//         String   texts="吃了吗";
//            String plyaid = userService.getopid(id);
//            // 人格 id，我们已经预设好了的
//            String roleid = userService.getroleid(name);
//
//            String chatId = UUID.randomUUID().toString().substring(0, 10);
//            String preChatId = chatId;
//            List<InteractiveRequest.Text> text = new ArrayList<>();
//            InteractiveRequest.Text text1 = new InteractiveRequest.Text();
//            text1.setContent(texts);
//            text1.setRole("user");
//            text.add(text1);
//
//            InteractiveRequest interactiveRequest = buildInteractiveRequest(appId, plyaid, roleid, chatId, preChatId, text);
//
//            long ts = System.currentTimeMillis();
//            String signature = AuthUtil.getSignature(appId, secret, ts);
//            String requestUrl = interactiveUrl + chatId + "?" + "appId=" + appId + "&timestamp=" + ts + "&signature=" + signature;
//
//            final OkHttpClient okHttpClient = new OkHttpClient().newBuilder().build();
//            final StringBuffer buffer = new StringBuffer();
//
//            Request request = new Request.Builder()
//                    .url(requestUrl)
//                    .build();
//
//            WebSocket ws = okHttpClient.newWebSocket(request, new WebSocketListener() {
//                @Override
//                public void onClosed(@NotNull WebSocket webSocket, int code, @NotNull String reason) {
//                    logger.info("websocket close. Reason: {}", reason);
//                    webSocket.close(1002, "websocket finish");
//                    okHttpClient.connectionPool().evictAll();
//                }
//
//                @Override
//                public void onFailure(@NotNull WebSocket webSocket, @NotNull Throwable t, @Nullable Response response) {
//                    logger.error("websocket failure. Error: {}", t.getMessage());
//                    webSocket.close(1001, "websocket finish");
//                    okHttpClient.connectionPool().evictAll();
//                }
//
//                @Override
//                public void onMessage(@NotNull WebSocket webSocket, @NotNull String text) {
//                    try {
//                        InteractiveResponse response = JSON.parseObject(text, InteractiveResponse.class);
//                        if (response.getHeader().getCode() == 0) {
//                            List<InteractiveResponse.Text> textList = response.getPayload().getChoices().getText();
//                            buffer.append(textList.get(0).getContent());
//                            if (response.getHeader().getStatus() == 2) {
//                                logger.info("回答结束，回答内容：{}", buffer);
//                                logger.info("本轮问答用量：{}", JSONUtil.toJsonStr(response.getPayload().getUsage()));
//                                webSocket.close(1000, "websocket finish");
//                                okHttpClient.connectionPool().evictAll();
//                            }
//                        }
//                    } catch (Exception e) {
//                        logger.error("会话异常！异常信息：{}", text);
//                        webSocket.close(1000, "websocket error");
//                    }
//                }
//
//                @Override
//                public void onOpen(@NotNull WebSocket webSocket, @NotNull Response response) {
//                    webSocket.send(JSON.toJSONString(interactiveRequest));
//                }
//            });
//
//            return new ResponseEntity<>(HttpStatus.OK);
//        }
//
//        catch (Exception e) {
//            logger.error("处理用户输入时出现异常：", e);
//            return new ResponseEntity<>(HttpStatus.INTERNAL_SERVER_ERROR);
//        }
//    }
//
//    private InteractiveRequest buildInteractiveRequest(String appId, String userId, String agentId, String chatId, String preChatId, List<InteractiveRequest.Text> text) {
//        InteractiveRequest interactiveRequest = new InteractiveRequest();
//        InteractiveRequest.Header header = new InteractiveRequest.Header();
//        header.setApp_id(appId);
//        header.setUid(userId);
//        header.setAgent_id(agentId);
//        interactiveRequest.setHeader(header);
//        InteractiveRequest.Parameter parameter = new InteractiveRequest.Parameter();
//        InteractiveRequest.Chat chat = new InteractiveRequest.Chat();
//        chat.setChat_id(chatId);
//        chat.setPre_chat_id(preChatId);
//        parameter.setChat(chat);
//        interactiveRequest.setParameter(parameter);
//        InteractiveRequest.Payload payload = new InteractiveRequest.Payload();
//        InteractiveRequest.Message message = new InteractiveRequest.Message();
//        message.setText(text);
//        payload.setMessage(message);
//        interactiveRequest.setPayload(payload);
//        return interactiveRequest;
//    }
//}
