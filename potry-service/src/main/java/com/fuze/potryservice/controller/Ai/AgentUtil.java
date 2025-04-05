package com.fuze.potryservice.controller.Ai;

import com.alibaba.fastjson.JSONArray;
import com.alibaba.fastjson.JSONObject;
import com.alibaba.fastjson.TypeReference;
import com.fuze.dto.AgentCharactersDto;
import com.fuze.potryservice.mapper.UserMapper;
import com.fuze.response.AgentCharacter;
import com.fuze.response.ResponseMsg;
import com.fuze.utils.AuthUtil;
import okhttp3.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Controller;
import org.springframework.stereotype.Service;


/**
 * Created with IntelliJ IDEA
 *
 * @author zhwang40
 * @date：2024/3/21
 * @time：10:36
 * @descripion:
 */
@Service
public class AgentUtil {
    @Autowired
    private UserMapper userMapper;
    private final static OkHttpClient client = new OkHttpClient();
    private static final String suffixUrl = "/open/agent";
    public void createAgentCharacter(String url, String appId, String secret, String playerId, String agentName, String agentType, String desc, String perso, JSONArray languag, String identity, String hobby) throws Exception {
        url = url + suffixUrl + "/edit-character";
        System.out.println("url:" + url);
        AgentCharactersDto charactersDto = AgentCharactersDto.builder()
                .appId(appId)
                .playerId(playerId)
                .agentName(agentName)
                .agentType(agentType)
                .personalityDescription(perso)
                .languageStyle(languag)
                .identity(identity)
                .hobby(hobby)
                .description(desc).build();
        RequestBody requestBody = RequestBody.create(MediaType.parse("application/json; charset=utf-8"), JSONObject.toJSONString(charactersDto));
        long ts = System.currentTimeMillis();
        Request request = new Request.Builder()
                .url(url)
                .post(requestBody)
                .addHeader("appId", appId)
                .addHeader("timestamp", String.valueOf(ts))
                .addHeader("signature", AuthUtil.getSignature(appId, secret, ts))
                .build();
        Response response = client.newCall(request).execute();
        ResponseMsg<String> responseMsg = JSONObject.parseObject(response.body().string(), new TypeReference<ResponseMsg<String>>() {
        });
        String data=responseMsg.getData();
        System.out.println(data);
        userMapper.setAgentId(agentName, data);


        if (responseMsg.getCode() != 10000) {
            throw new Exception("创建人格失败，responseMsg =" + responseMsg);
        }

    }

    public void editAgentCharacter(String url, String appId, String secret, String playerId, String agentId, String agentName, String agentType, String desc) throws Exception {
        url = url + suffixUrl + "/edit-character";
        System.out.println("url:" + url);
        AgentCharactersDto charactersDto = AgentCharactersDto.builder()
                .appId(appId)
                .agentId(agentId)
                .playerId(playerId)
                .agentName(agentName)
                .agentType(agentType)
                .description(desc).build();
        RequestBody requestBody = RequestBody.create(MediaType.parse("application/json; charset=utf-8"), JSONObject.toJSONString(charactersDto));
        long ts = System.currentTimeMillis();
        Request request = new Request.Builder()
                .url(url)
                .post(requestBody)
                .addHeader("appId", appId)
                .addHeader("timestamp", String.valueOf(ts))
                .addHeader("signature", AuthUtil.getSignature(appId, secret, ts))
                .build();
        Response response = client.newCall(request).execute();
        ResponseMsg<String> responseMsg = JSONObject.parseObject(response.body().string(), new TypeReference<ResponseMsg<String>>() {
        });
        System.out.println(responseMsg);
        if (responseMsg.getCode() != 10000) {
            throw new Exception("编辑人格失败，responseMsg =" + responseMsg);
        }
    }

    public void getAgentCharacter(String url, String appId, String secret, String agentId) throws Exception {
        url = url + suffixUrl + "/get-character";
        StringBuilder sb = new StringBuilder();
        sb.append(url).append("?appId=").append(appId).append("&agentId=").append(agentId);
        System.out.println("url:" + sb);
        long ts = System.currentTimeMillis();
        Request request = new Request.Builder()
                .url(sb.toString())
                .addHeader("appId", appId)
                .addHeader("timestamp", String.valueOf(ts))
                .addHeader("signature", AuthUtil.getSignature(appId, secret, ts))
                .build();
        Response response = client.newCall(request).execute();
        ResponseMsg<AgentCharacter> responseMsg = JSONObject.parseObject(response.body().string(), new TypeReference<ResponseMsg<AgentCharacter>>() {
        });
        System.out.println(responseMsg);
        if (responseMsg.getCode() != 10000) {
            throw new Exception("获取人格失败，responseMsg =" + responseMsg);
        }
    }

    public void deleteAgentCharacter(String url, String appId, String secret, String agentId,String agentName) throws Exception {
        url = url + suffixUrl + "/delete-character";
        StringBuilder sb = new StringBuilder();
        sb.append(url).append("?appId=").append(appId).append("&agentId=").append(agentId).append("&agentName=").append(agentName);
        System.out.println("url:" + sb);
        long ts = System.currentTimeMillis();
        Request request = new Request.Builder()
                .url(sb.toString())
                .delete()
                .addHeader("appId", appId)
                .addHeader("timestamp", String.valueOf(ts))
                .addHeader("signature", AuthUtil.getSignature(appId, secret, ts))
                .build();
        Response response = client.newCall(request).execute();
        ResponseMsg<Boolean> responseMsg = JSONObject.parseObject(response.body().string(), new TypeReference<ResponseMsg<Boolean>>() {
        });
        System.out.println(responseMsg);
        if (responseMsg.getCode() != 10000) {
            throw new Exception("删除人格失败，responseMsg =" + responseMsg);
        }
    }

}
