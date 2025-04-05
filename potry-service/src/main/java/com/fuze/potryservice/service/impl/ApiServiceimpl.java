package com.fuze.potryservice.service.impl;

import com.fuze.constant.ApiAuthAlgorithm;
import com.fuze.potryservice.service.ApiService;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;


@Service
public class ApiServiceimpl implements ApiService {
    @Override
    public String sendRequest(String appId, String secret) {
        Long timestamp = System.currentTimeMillis();
        String signature = ApiAuthAlgorithm.getSignature(appId, secret, timestamp);

        // 创建 URL 对象
        URL url = null;
        try {
            url = new URL("http://example.com/api");
            HttpURLConnection connection = (HttpURLConnection) url.openConnection();

            // 设置请求方法
            connection.setRequestMethod("GET");

            // 设置请求头
            connection.setRequestProperty("appId", appId);
            connection.setRequestProperty("timestamp", timestamp.toString());
            connection.setRequestProperty("signature", signature);

            // 发送请求
            int responseCode = connection.getResponseCode();

            // 读取响应
            BufferedReader in = new BufferedReader(new InputStreamReader(connection.getInputStream()));
            String inputLine;
            StringBuilder content = new StringBuilder();
            while ((inputLine = in.readLine()) != null) {
                content.append(inputLine);
            }
            in.close();

            // 返回响应内容
            return content.toString();

        } catch (Exception e) {
            throw new RuntimeException("Failed to send request", e);
        }
    }

}
