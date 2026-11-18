package com.fuze.utils;

import com.aliyun.oss.ClientException;
import com.aliyun.oss.OSS;
import com.aliyun.oss.OSSClientBuilder;
import com.aliyun.oss.OSSException;
import com.fuze.properties.AliOssProperties;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.io.ByteArrayInputStream;
import java.util.UUID;

@Data
@Component
@Slf4j
@NoArgsConstructor
@AllArgsConstructor
public class AliOssUtil {

    @Autowired(required = false)
    private AliOssProperties aliOssProperties;

    private String endpoint;
    private String accessKeyId;
    private String accessKeySecret;
    private String bucketName;

    public AliOssUtil(String endpoint, String accessKeyId, String accessKeySecret, String bucketName) {
        this.endpoint = endpoint;
        this.accessKeyId = accessKeyId;
        this.accessKeySecret = accessKeySecret;
        this.bucketName = bucketName;
    }

    private String getEffectiveEndpoint() {
        if (aliOssProperties != null && aliOssProperties.getEndpoint() != null && !aliOssProperties.getEndpoint().isEmpty()) {
            return aliOssProperties.getEndpoint();
        }
        return endpoint != null ? endpoint : System.getenv("ALIOSS_ENDPOINT");
    }

    private String getEffectiveAccessKeyId() {
        if (aliOssProperties != null && aliOssProperties.getAccessKeyId() != null && !aliOssProperties.getAccessKeyId().isEmpty()) {
            return aliOssProperties.getAccessKeyId();
        }
        return accessKeyId != null ? accessKeyId : System.getenv("ALIOSS_ACCESS_KEY_ID");
    }

    private String getEffectiveAccessKeySecret() {
        if (aliOssProperties != null && aliOssProperties.getAccessKeySecret() != null && !aliOssProperties.getAccessKeySecret().isEmpty()) {
            return aliOssProperties.getAccessKeySecret();
        }
        return accessKeySecret != null ? accessKeySecret : System.getenv("ALIOSS_ACCESS_KEY_SECRET");
    }

    private String getEffectiveBucketName() {
        if (aliOssProperties != null && aliOssProperties.getBucketName() != null && !aliOssProperties.getBucketName().isEmpty()) {
            return aliOssProperties.getBucketName();
        }
        return bucketName != null ? bucketName : System.getenv("ALIOSS_BUCKET_NAME");
    }

    /**
     * 文件上传
     *
     * @param bytes
     * @param objectName
     * @return
     */
    public String upload(byte[] bytes, String objectName) {
        String ep = getEffectiveEndpoint();
        String ak = getEffectiveAccessKeyId();
        String sk = getEffectiveAccessKeySecret();
        String bn = getEffectiveBucketName();

        if (ep == null || ak == null || sk == null || bn == null) {
            log.error("阿里云 OSS 凭据未配置，无法执行上传。请配置 sky.alioss 或相关环境变量。");
            throw new IllegalStateException("阿里云 OSS 凭据未配置");
        }

        // 创建OSSClient实例。
        OSS ossClient = new OSSClientBuilder().build(ep, ak, sk);

        try {
            // 创建PutObject请求。
            ossClient.putObject(bn, objectName, new ByteArrayInputStream(bytes));
        } catch (OSSException oe) {
            System.out.println("Caught an OSSException, which means your request made it to OSS, "
                    + "but was rejected with an error response for some reason.");
            System.out.println("Error Message:" + oe.getErrorMessage());
            System.out.println("Error Code:" + oe.getErrorCode());
            System.out.println("Request ID:" + oe.getRequestId());
            System.out.println("Host ID:" + oe.getHostId());
        } catch (ClientException ce) {
            System.out.println("Caught an ClientException, which means the client encountered "
                    + "a serious internal problem while trying to communicate with OSS, "
                    + "such as not being able to access the network.");
            System.out.println("Error Message:" + ce.getMessage());
        } finally {
            if (ossClient != null) {
                ossClient.shutdown();
            }
        }
        //文件访问路径规则 https://BucketName.Endpoint/ObjectName
        StringBuilder stringBuilder = new StringBuilder("https://");
        stringBuilder
                .append(bn)
                .append(".")
                .append(ep)
                .append("/")
                .append(objectName);

        log.info("文件上传到:{}", stringBuilder.toString());

        return stringBuilder.toString();
    }
}
