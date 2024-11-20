package com.fuze.potryservice.controller.Ai;

import com.fuze.potryservice.service.PotryService;
import com.fuze.result.Result;
import com.google.gson.JsonElement;
import com.google.gson.JsonParser;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import okhttp3.HttpUrl;
import org.eclipse.angus.mail.util.BASE64DecoderStream;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.*;

import static org.apache.commons.lang3.StringEscapeUtils.escapeJson;

@RestController
@RequestMapping("/user/AI/draow")
@Api(tags ="Ai绘画")
@Slf4j
public class AiDraow {
    @Autowired
private PotryService potryService;
    private static final String hostUrl = "https://spark-api.cn-huabei-1.xf-yun.com/v2.1/tti";
    private static final String appid = "5bb3fb4a";
    private  static final String apiSecret = "OGM1MTBmZjlmYTc5ZDI1MDg2Y2NhMzRk";
    private static final String apiKey = "cb7c66763c4ce97127e003ed70b59729";

    @ApiOperation("绘画,根据古诗id来进行绘画")
    @PostMapping("")
    public Result<String> draw(@RequestParam Integer id) throws Exception {
        String authUrl = getAuthUrl(hostUrl, apiKey, apiSecret);

String ai=potryService.GetContentById(id).getContent();
        String escapedAi = escapeJson(ai+"生成全景图(panorama)");
        // URL地址正确
        System.err.println(authUrl);
        String json = "{\n" +
                "  \"header\": {\n" +
                "    \"app_id\": \"" + appid + "\",\n" +
                "    \"uid\": \"" + UUID.randomUUID().toString().substring(0, 15) + "\"\n" +
                "  },\n" +
                "  \"parameter\": {\n" +
                "    \"chat\": {\n" +
                "      \"domain\": \"s291394db\",\n" +
                "      \"temperature\": 0.5,\n" +
                "      \"max_tokens\": 4096,\n" +
                "      \"width\": 512,\n" +
                "      \"height\": 512\n" +
                "    }\n" +
                "  },\n" +
                "  \"payload\": {\n" +
                "    \"message\": {\n" +
                "      \"text\": [\n" +
                "        {\n" +
                "          \"role\": \"user\",\n" +
                "          \"content\": \""+escapedAi+"\"\n" +
                "        }\n" +
                "      ]\n" +
                "    }\n" +
                "  }\n" +
                "}";
        // 发起Post请求
//        System.err.println(json);
        String res = MyUtil.doPostJson(authUrl, null, json);
        JsonParser parser = new JsonParser();
        JsonElement parse = parser.parse(res);
        String payload = parse.getAsJsonObject()
                .get("payload").getAsJsonObject()
                .get("choices").getAsJsonObject()
                .get("text").getAsJsonArray()
                .get(0).getAsJsonObject()
                .get("content").getAsJsonPrimitive().getAsString();
        return Result.success(payload);
    }
    @ApiOperation("绘画,根据用户传来的对话来进行绘画")
    @PostMapping("/sdadwadw")
    public Result<String> draw(@RequestParam String ai) throws Exception {
        String authUrl = getAuthUrl(hostUrl, apiKey, apiSecret);
        String escapedAi = escapeJson(ai+"生成全景图(panorama)");
        // URL地址正确
        System.err.println(authUrl);
        String json = "{\n" +
                "  \"header\": {\n" +
                "    \"app_id\": \"" + appid + "\",\n" +
                "    \"uid\": \"" + UUID.randomUUID().toString().substring(0, 15) + "\"\n" +
                "  },\n" +
                "  \"parameter\": {\n" +
                "    \"chat\": {\n" +
                "      \"domain\": \"s291394db\",\n" +
                "      \"temperature\": 0.5,\n" +
                "      \"max_tokens\": 4096,\n" +
                "      \"width\": 512,\n" +
                "      \"height\": 512\n" +
                "    }\n" +
                "  },\n" +
                "  \"payload\": {\n" +
                "    \"message\": {\n" +
                "      \"text\": [\n" +
                "        {\n" +
                "          \"role\": \"user\",\n" +
                "          \"content\": \""+escapedAi+"\"\n" +
                "        }\n" +
                "      ]\n" +
                "    }\n" +
                "  }\n" +
                "}";
        // 发起Post请求
//        System.err.println(json);
        String res = MyUtil.doPostJson(authUrl, null, json);
        JsonParser parser = new JsonParser();
        JsonElement parse = parser.parse(res);
        String payload = parse.getAsJsonObject()
                .get("payload").getAsJsonObject()
                .get("choices").getAsJsonObject()
                .get("text").getAsJsonArray()
                .get(0).getAsJsonObject()
                .get("content").getAsJsonPrimitive().getAsString();

        String payload1 = "data:image/png;base64,"+payload;
      String resultString = payload1.replace("\"", "");
        return Result.success(resultString);
    }
    public static String getAuthUrl(String hostUrl, String apiKey, String apiSecret) throws Exception {
        URL url = new URL(hostUrl);
        // 时间
        SimpleDateFormat format = new SimpleDateFormat("EEE, dd MMM yyyy HH:mm:ss z", Locale.US);
        format.setTimeZone(TimeZone.getTimeZone("GMT"));
        String date = format.format(new Date());
        // date="Thu, 12 Oct 2023 03:05:28 GMT";
        // 拼接
        String preStr = "host: " + url.getHost() + "\n" + "date: " + date + "\n" + "POST " + url.getPath() + " HTTP/1.1";
        // System.err.println(preStr);
        // SHA256加密
        Mac mac = Mac.getInstance("hmacsha256");
        SecretKeySpec spec = new SecretKeySpec(apiSecret.getBytes(StandardCharsets.UTF_8), "hmacsha256");
        mac.init(spec);

        byte[] hexDigits = mac.doFinal(preStr.getBytes(StandardCharsets.UTF_8));
        // Base64加密
        String sha = Base64.getEncoder().encodeToString(hexDigits);
        // System.err.println(sha);
        // 拼接
        String authorization = String.format("api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"", apiKey, "hmac-sha256", "host date request-line", sha);
        // 拼接地址
        HttpUrl httpUrl = Objects.requireNonNull(HttpUrl.parse("https://" + url.getHost() + url.getPath())).newBuilder().//
                addQueryParameter("authorization", Base64.getEncoder().encodeToString(authorization.getBytes(StandardCharsets.UTF_8))).//
                addQueryParameter("date", date).//
                addQueryParameter("host", url.getHost()).//
                build();

        // System.err.println(httpUrl.toString());
        return httpUrl.toString();
    }
}
