package com.fuze.utils;

import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.JSONObject;
import com.alibaba.fastjson.TypeReference;
import com.fuze.dto.PlayerDto;
import com.fuze.response.ResponseMsg;
import okhttp3.*;




/**
 * @Author: yxliu37
 * @Date: 2024/3/21 16:07
 * @Description: 玩家相关
 */
public class PlayerUtil {

    private final static OkHttpClient client = new OkHttpClient();

    private static final String suffixUrl = "/open/player";

    /**
     * 检查玩家是否注册
     * @param url
     * @param appId
     * @param secret
     * @param playerName
     * @throws Exception
     */
    public void ifRegister(String url, String appId, String secret, String playerName) throws Exception {
        url = url + suffixUrl + "/if-register"
                + "?appId=" + appId
                + "&playerName=" + playerName;
        System.out.println("url:" + url);
        long ts = System.currentTimeMillis();
        Request request = new Request.Builder()
                .url(url)
                .get()
                .addHeader("appId", appId)
                .addHeader("timestamp", String.valueOf(ts))
                .addHeader("signature", AuthUtil.getSignature(appId, secret, ts))
                .build();
        Response response = client.newCall(request).execute();
        ResponseMsg<String> responseMsg = JSONObject.parseObject(response.body().string(), new TypeReference<ResponseMsg<String>>() {
        });
        System.out.println(responseMsg);
        if (responseMsg.getCode() != 10000) {
            throw new Exception("查询失败，responseMsg =" + responseMsg);
        }
    }

    /**
     * 注册玩家
     * @param url
     * @param appId
     * @param secret
     * @param playerName
     * @param playerType
     * @param desc
     * @throws Exception
     */
    public String register(String url, String appId, String secret, String playerName, String playerType, String desc) throws Exception {
        url = url + suffixUrl + "/register";
        System.out.println("url:" + url);
        PlayerDto playerDto = PlayerDto.builder()
                .appId(appId)
                .playerName(playerName)
                .playerType(playerType)
                .description(desc).build();
        RequestBody requestBody = RequestBody.create(MediaType.parse("application/json; charset=utf-8"),JSON.toJSONString(playerDto));
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
            throw new Exception("注册玩家失败，responseMsg =" + responseMsg);
        }
        return responseMsg.getData();
    }

    /**
     * 编辑玩家信息
     * @param url
     * @param appId
     * @param secret
     * @param playerId
     * @param playerName
     * @param playerType
     * @param desc
     * @throws Exception
     */
    public void modify(String url, String appId, String secret, String playerId, String playerName, String playerType, String desc) throws Exception {
        url = url + suffixUrl + "/modify";
        System.out.println("url:" + url);
        PlayerDto playerDto = PlayerDto.builder()
                .playerId(playerId)
                .appId(appId)
                .playerName(playerName)
                .playerType(playerType)
                .description(desc).build();
        RequestBody requestBody = RequestBody.create(MediaType.parse("application/json; charset=utf-8"), JSON.toJSONString(playerDto));
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
            throw new Exception("编辑玩家失败，responseMsg =" + responseMsg);
        }
    }

    /**
     * 删除玩家
     * @param url
     * @param appId
     * @param secret
     * @param playerId
     * @param playerName
     * @throws Exception
     */
    public void delete(String url, String appId, String secret, String playerId, String playerName) throws Exception {
        url = url + suffixUrl + "/delete";
        System.out.println("url:" + url);
        PlayerDto playerDto = PlayerDto.builder()
                .playerId(playerId)
                .appId(appId)
                .playerName(playerName).build();
        RequestBody requestBody = RequestBody.create(MediaType.parse("application/json; charset=utf-8"), JSON.toJSONString(playerDto));
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
            throw new Exception("编辑玩家失败，responseMsg =" + responseMsg);
        }
    }
}
