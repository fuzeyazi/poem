package com.fuze.constant;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.InvalidKeyException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SignatureException;
import java.util.Base64;

public class ApiAuthAlgorithm {

    private static final char[] MD5_TABLE = {
            '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
            'a', 'b', 'c', 'd', 'e', 'f'
    };

    /**
     * 获取签名
     *
     * @param appId    应用 ID
     * @param secret   接口密钥
     * @param timestamp 时间戳（毫秒）
     * @return 返回签名
     */
    public   static   String    getSignature(String appId, String secret, long timestamp) {
        try {
            ApiAuthAlgorithm a= new ApiAuthAlgorithm();
            String auth = a.md5(appId + timestamp);
            return a.hmacSHA1Encrypt(auth, secret);
        } catch (SignatureException e) {
            return null;
        }
    }

    /**
     * SHA1加密
     *
     * @param encryptText 加密文本
     * @param encryptKey  加密键
     * @return 加密结果
     * @throws SignatureException 如果加密失败
     */
    private String hmacSHA1Encrypt(String encryptText, String encryptKey)
            throws SignatureException {
        byte[] rawHmac;
        try {
            byte[] data = encryptKey.getBytes(StandardCharsets.UTF_8);
            SecretKeySpec secretKey = new SecretKeySpec(data, "HmacSHA1");
            Mac mac = Mac.getInstance("HmacSHA1");
            mac.init(secretKey);
            byte[] text = encryptText.getBytes(StandardCharsets.UTF_8);
            rawHmac = mac.doFinal(text);
        } catch (InvalidKeyException | NoSuchAlgorithmException e) {
            throw new SignatureException("Encryption error: " + e.getMessage());
        }
        return new String(Base64.getEncoder().encode(rawHmac));
    }

    /**
     * MD5加密
     *
     * @param cipherText 待加密文本
     * @return 加密后的字符串
     */
    private String md5(String cipherText) {
        try {
            byte[] data = cipherText.getBytes();
            MessageDigest mdInst = MessageDigest.getInstance("MD5");
            mdInst.update(data);
            byte[] md = mdInst.digest();

            int j = md.length;
            char[] str = new char[j * 2];
            int k = 0;
            for (byte byte0 : md) {
                str[k++] = MD5_TABLE[byte0 >>> 4 & 0xf];
                str[k++] = MD5_TABLE[byte0 & 0xf];
            }
            return new String(str);
        } catch (Exception e) {
            return null;
        }
    }
}