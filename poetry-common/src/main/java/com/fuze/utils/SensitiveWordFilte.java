package com.fuze.utils;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Component;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.Base64;
import java.util.HashSet;
import java.util.Set;
import java.util.regex.Pattern;

@Component
public class SensitiveWordFilte {

    private static final String FILE_PATH = "sensi_word/keywords.txt";
    private static SensitiveWordFilte instance;
    private static final Object lock = new Object();
    private Set<String> sensitiveWords = new HashSet<>();
    private Pattern pattern;

    // 私有构造函数，确保外部无法直接实例化
    private SensitiveWordFilte() {
        try {
            loadSensitiveWordsFromFile();
        } catch (IOException e) {
            throw new RuntimeException("Failed to initialize SensitiveWordFilter", e);
        }
    }

    // 获取单例实例
    public static SensitiveWordFilte getInstance() {
        if (instance == null) {
            synchronized (lock) {
                if (instance == null) {
                    instance = new SensitiveWordFilte();
                }
            }
        }
        return instance;
    }

    // 加载敏感词从文件
    private void loadSensitiveWordsFromFile() throws IOException {
        Resource resource = new ClassPathResource(FILE_PATH);
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(resource.getInputStream()))) {
            SensitiveWordLoader loader = new SensitiveWordLoader();
            this.sensitiveWords = loader.loadSensitiveWords(reader);
            buildPattern();
        }
    }

    // 构建正则表达式模式
    private void buildPattern() {
        if (sensitiveWords == null || sensitiveWords.isEmpty()) {
            pattern = null;
        } else {
            String regex = sensitiveWords.stream()
                    .filter(w -> w != null && !w.trim().isEmpty())
                    .map(this::escapeSpecialChars)
                    .reduce((a, b) -> a + "|" + b)
                    .orElse("");
            if (regex.isEmpty()) {
                pattern = null;
            } else {
                pattern = Pattern.compile(regex, Pattern.UNICODE_CHARACTER_CLASS);
            }
        }
    }

    // 转义正则表达式特殊字符
    private String escapeSpecialChars(String word) {
        return Pattern.quote(word);
    }

    /**
     * 判断文本中是否包含敏感词
     * @param text 待检测文本
     * @return true 包含违规敏感词，false 干净合规
     */
    public boolean containsSensitiveWord(String text) {
        if (text == null || text.isEmpty() || pattern == null) {
            return false;
        }
        return pattern.matcher(text).find();
    }

    /**
     * 过滤文本校验（兼容老接口语义：是否通过合规校验）
     * @param text 待检测文本
     * @return true 干净合规放行，false 含有敏感词违规拦截
     */
    public Boolean filter(String text) {
        return !containsSensitiveWord(text);
    }

    // 内部类用于加载敏感词
    private static class SensitiveWordLoader {
        // 从 Base64 编码的读取流中加载敏感词
        public Set<String> loadSensitiveWords(BufferedReader reader) throws IOException {
            Set<String> sensitiveWords = new HashSet<>();
            String base64EncodedLine;
            while ((base64EncodedLine = reader.readLine()) != null) {
                byte[] decodedBytes = Base64.getDecoder().decode(base64EncodedLine);
                String decodedLine = new String(decodedBytes);
                for (String word : decodedLine.split("\n")) {
                    sensitiveWords.add(word.trim());
                }
            }
            return sensitiveWords;
        }
    }
}