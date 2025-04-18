package com.fuze.potryservice.service.impl;

import cn.hutool.core.date.DateUtil;
import com.fuze.dto.CommentAiDto;
import com.fuze.dto.PotryDTO;
import com.fuze.entity.Suggestion;
import com.fuze.potryservice.service.AdminService;
import com.fuze.potryservice.service.CommandService;
import com.fuze.potryservice.service.PotryService;
import lombok.Data;
import org.json.JSONArray;
import org.json.JSONObject;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class CommandServiceimpl implements CommandService {
    @Autowired
    private AdminService adminService;

    @Autowired
    private PotryService potryService;

    public Map<String, String> process(String command) {
        System.out.println("command:" + command);
        Map<String, String> result = new HashMap<>();
        JSONObject intent = callChatGPT(command);

        if (intent != null && intent.has("action")) {
            String action = intent.getString("action");
            System.out.println("action:" + action);
            switch (action) {
                case "add_poem": {
                    PotryDTO dto = new PotryDTO();
                    dto.setTitle(intent.optString("title", ""));
                    dto.setDynasty(intent.optString("dynasty", ""));
                    dto.setWriter(intent.optString("writer", ""));
                    dto.setContent(intent.optString("content", ""));
                    dto.setType(intent.optString("type", ""));
                    adminService.add(dto);
                    result.put("message", "已自动添加古诗：《" + dto.getTitle() + "》");
                    break;
                }
                case "update_poem": {
                    PotryDTO dto = new PotryDTO();
                    dto.setId(intent.optInt("id", 0));
                    dto.setTitle(intent.optString("title", ""));
                    dto.setDynasty(intent.optString("dynasty", ""));
                    dto.setWriter(intent.optString("writer", ""));
                    dto.setContent(intent.optString("content", ""));
                    dto.setType(intent.optString("type", ""));
                    adminService.update(dto);
                    result.put("message", "已修改古诗编号： " + dto.getId());
                    break;
                }
                case "delete_poemBYid": {
                    long id = intent.optLong("id", 0);
                    adminService.delete(java.util.List.of(id));
                    result.put("message", "已删除古诗编号： " + id);
                    break;
                }
                case "delete_poemBYtitle": {
                    String title = intent.optString("title", "");
                    adminService.deleteByTitle(title);
                    result.put("message", "已删除古诗标题： " + title);
                    break;
                }
                case "count_poem": {
                    int count = potryService.getcount();
                    result.put("message", "当前共有古诗数量： " + count);
                    break;
                }
                case "search_poem": {
                    PotryDTO dto = new PotryDTO();
                    dto.setId(intent.optInt("id", 0));
                    dto.setTitle(intent.optString("title", ""));
                    dto.setDynasty(intent.optString("dynasty", ""));
                    dto.setWriter(intent.optString("writer", ""));
                    dto.setContent(intent.optString("content", ""));
                    dto.setType(intent.optString("type", ""));
                    System.out.println(dto);
                    List<PotryDTO> content = adminService.GetContent(dto);
                    if (content.isEmpty()) {
                        result.put("message", "未查询到古诗");
                    } else {
                        result.put("message", "已查询古诗： " + content);
                    }
                    break;
                }
                default:
                    result.put("message", "未识别的操作类型");
            }
        } else {
            result.put("message", "无法解析用户意图");
        }

        return result;
    }

    @Override
    public Object process1(CommentAiDto commentAiDto,List<String> list) {
        Map<String, String> result = new HashMap<>();
        JSONObject intent = callChatGPT1(commentAiDto,list);

        if (intent.has("content")) {
            String content = intent.getString("content").trim();

            // 构建建议并保存
            Suggestion suggestion = Suggestion.builder()
                    .id(commentAiDto.getId())
                    .content(content) // 正确使用 content 字符串
                    .createdAt(DateUtil.now())
                    .build();

            adminService.save(suggestion);
            result.put("message", content);
        } else {
            // 错误信息处理
            result.put("message", "无法解析内容，请检查输入或联系管理员");
        }

        return result;
    }


    private JSONObject callChatGPT(String command) {
        try {
            String apiKey = "sk-v4yzSqtbttHco6e7wskObkfPhqAYan671q1KjRcS0BAbnV8f"; // 安全起见建议放在配置文件里
            String url = "https://xiaoai.plus/v1/chat/completions";
            String prompt = """
                    你是一个专门用于管理古诗的智能助手。你的任务是从用户的指令中提取出操作类型及相关字段并以 JSON 格式返回。你需要识别用户的意图并根据不同的操作类型提取必要字段。如果无法确定用户意图，请返回 {"action": "unknown"}。
                    注意：
                            - 必须以 `{` 开始。
                            - 不要添加多余的文字说明、注释或解释。
                            - 输出必须是标准 JSON 格式。
                    【操作类型】（字段：action） \s
                    你可以识别并返回以下操作类型：
                    - add_poem：添加一首古诗
                    - update_poem：修改已存在的古诗
                    - delete_poemBYid：通过识别id来删除已存在的古诗
                    - count_poem：统计现存古诗数量
                    - search_poem：搜索古诗（可以按作者、标题等条件）
                    -delete_poemBYtitle:通过识别title来删除已存在的古诗
                    
                    【必需字段】 \s
                    - action：表示操作类型，必须返回以下值之一：`add_poem`, `update_poem`, `delete_poemBYid`, `count_poem`, `search_poem`,`delete_poemBYtitle`。
                    
                    【可选字段】 \s
                    - id：古诗的编号，仅对 `update_poem` 或 `delete_poemBYid` 操作有效。
                    - title：诗名，仅对 `add_poem`、`update_poem` 和 `search_poem` 和`delete_poemBYtitle`操作有效。
                    - dynasty：朝代（如唐代、宋代等），仅对 `add_poem`、`update_poem` 和 `search_poem` 操作有效。
                    - writer：作者，仅对 `add_poem`、`update_poem` 和 `search_poem` 操作有效。
                    - content：古诗内容，仅对 `add_poem` 和 `update_poem` 操作有效。
                    - type：诗歌类型（如写景、咏史、抒情等），仅对 `add_poem` 和 `update_poem` 操作有效。
                    【特殊情况】\s
                    当识别action为add_poem时，如果其中他的字段writer和content和dynasty都为空的话，你需要联网搜索将这首诗
                    
                    【示例】 \s
                    用户说：我想添加一首李白的诗，叫《静夜思》，内容是“床前明月光”，这是唐代的诗，类型是写景。 \s
                    {
                      "action": "add_poem",
                      "title": "静夜思",
                      "dynasty": "唐代",
                      "writer": "李白",
                      "content": "床前明月光，疑是地上霜。举头望明月，低头思故乡。",
                      "type": "写景"
                    }
                    
              
                    
            现在用户输入：""" + command;


            // 构建请求体
            JSONObject message = new JSONObject();
            message.put("role", "user");
            message.put("content", prompt);

            JSONObject body = new JSONObject();
            body.put("model", "gpt-4");
            body.put("messages", new org.json.JSONArray().put(message));

            // 构建请求
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .header("Authorization", "Bearer " + apiKey)
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body.toString()))
                    .build();

            // 发送请求
            HttpClient client = HttpClient.newHttpClient();
            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

            // 输出原始结果供调试
            System.out.println("==[AI Response]==");
            System.out.println(response.body());

            // 尝试解析
            JSONObject responseJson = new JSONObject(response.body());
            String content = responseJson
                    .getJSONArray("choices")
                    .getJSONObject(0)
                    .getJSONObject("message")
                    .getString("content")
                    .trim();

            // 有些模型返回值可能带```json或其他包裹，我们要清洗一下
            if (content.startsWith("```")) {
                content = content.replaceAll("```json", "")
                        .replaceAll("```", "")
                        .trim();
            }

            // 输出清洗后的内容供调试
            System.out.println("==[Parsed JSON Content]==");
            System.out.println(content);

            // 返回解析后的 JSON 对象
            return new JSONObject(content);

        } catch (Exception e) {
            System.err.println("AI 调用或解析失败：" + e.getMessage());
            e.printStackTrace();
            return null;
        }
    }

//public Map<String, String> process(String command) {
//        Map<String, String> result = new HashMap<>();
//        JSONObject intent = callDeepSeek(command);
//
//    // 更详细的错误诊断
//    if(intent == null) {
//        result.put("message", "API调用失败，请检查网络连接");
//        return result;
//    }
//
//    if(intent.has("error")) {
//        result.put("message", "DeepSeek服务错误: " + intent.getString("error"));
//        return result;
//    }
//
//    if (!intent.has("action") || intent.isNull("action")) {
//        // 添加诊断信息
//        String diagnostic = "响应内容: " + intent.toString();
//        System.err.println("无法解析用户意图. " + diagnostic);
//
//        result.put("message", "无法理解您的指令，请确保提供了有效的 'action' 参数");
//        result.put("suggestion", "例如: '添加李白的《静夜思》' 或 '删除id为123的古诗'");
//        return result;
//    }
//    String action = intent.optString("action", null);
//    if (action == null || action.isEmpty()) {
//        // 如果 "action" 为空或无效，返回错误信息
//        result.put("message", "无法理解您的指令，请确保 'action' 参数有效");
//        result.put("suggestion", "例如: 'add_poem', 'delete_poem' 等");
//        return result;
//    }
//        try {
//            switch (action) {
//                case "add_poem": {
//                    PotryDTO dto = new PotryDTO();
//                    dto.setTitle(intent.optString("title", "未命名"));
//                    dto.setDynasty(intent.optString("dynasty", "未知朝代"));
//                    dto.setWriter(intent.optString("writer", "未知作者"));
//                    dto.setContent(intent.optString("content", "暂无内容"));
//                    dto.setType(intent.optString("type", "未知类型"));
//                    adminService.add(dto);
//                    result.put("message", "已自动添加古诗：《" + dto.getTitle() + "》");
//                    break;
//                }
//                case "update_poem": {
//                    PotryDTO dto = new PotryDTO();
//                    dto.setId(intent.optInt("id", 0));
//                    dto.setTitle(intent.optString("title", "未命名"));
//                    dto.setDynasty(intent.optString("dynasty", "未知朝代"));
//                    dto.setWriter(intent.optString("writer", "未知作者"));
//                    dto.setContent(intent.optString("content", "暂无内容"));
//                    dto.setType(intent.optString("type", "未知类型"));
//                    adminService.update(dto);
//                    result.put("message", "已修改古诗编号：" + dto.getId());
//                    break;
//                }
//                case "delete_poem": {
//                    long id = intent.optLong("id", 0);
//                    adminService.delete(List.of(id));
//                    result.put("message", "已删除古诗编号：" + id);
//                    break;
//                }
//                case "count_poem": {
//                    int count = potryService.getcount();
//                    result.put("message", "当前共有古诗数量：" + count);
//                    break;
//                }
//                default:
//                    result.put("message", "未识别的操作类型：" + action);
//            }
//        } catch (Exception e) {
//            result.put("message", "执行操作时出错：" + e.getMessage());
//        }
//
//        return result;
//    }
//
//    private JSONObject callDeepSeek(String command) {
//        try {
//            String apiKey = "sk-b1a7a755de1849fa8e498c40fbb5ca60"; // 应从配置读取
//            String url = "https://api.deepseek.com/v1/chat/completions";
//
//            // 优化后的prompt
//            String prompt = """
//        你是一个古诗管理助手，请严格按以下规则处理用户指令：
//
//        1. 必须识别的操作类型(必须且只能是以下之一):
//           - add_poem: 当用户要添加古诗时使用
//           - update_poem: 当用户要修改已有古诗时使用
//           - delete_poem: 当用户要删除古诗时使用
//           - count_poem: 当用户要查询古诗数量时使用
//
//        2. 必须包含的字段:
//           - action(字符串): 上述操作类型之一
//           - id(数字): 仅update_poem和delete_poem时需要
//           - title(字符串): 古诗标题
//           - writer(字符串): 作者
//           - content(字符串): 古诗内容
//
//        3. 输出要求:
//           - 必须使用严格JSON格式
//           - 只包含用户指令中明确提到的字段
//           - 不要添加任何解释性文字
//           - 示例: {"action":"add_poem","title":"静夜思","writer":"李白","content":"床前明月光"}
//
//        用户指令: """ + command;
//
//            JSONObject body = new JSONObject();
//            body.put("model", "deepseek-chat");
//
//            JSONArray messages = new JSONArray();
//            messages.put(new JSONObject()
//                    .put("role", "system")
//                    .put("content", "你只返回JSON格式的操作指令，不包含任何解释"));
//
//            messages.put(new JSONObject()
//                    .put("role", "user")
//                    .put("content", prompt));
//
//            body.put("messages", messages);
//            body.put("temperature", 0.1); // 更低的随机性
//            body.put("max_tokens", 300);
//
//            HttpRequest request = HttpRequest.newBuilder()
//                    .uri(URI.create(url))
//                    .header("Authorization", "Bearer " + apiKey)
//                    .header("Content-Type", "application/json")
//                    .timeout(Duration.ofSeconds(30))
//                    .POST(HttpRequest.BodyPublishers.ofString(body.toString()))
//                    .build();
//
//            HttpResponse<String> response = HttpClient.newHttpClient()
//                    .send(request, HttpResponse.BodyHandlers.ofString());
//
//            if (response.statusCode() != 200) {
//                throw new RuntimeException("API请求失败，状态码：" + response.statusCode());
//            }
//
//            JSONObject responseJson = new JSONObject(response.body());
//            String content = responseJson.getJSONArray("choices")
//                    .getJSONObject(0)
//                    .getJSONObject("message")
//                    .getString("content");
//
//            // 增强的响应清理
//            content = content.trim()
//                    .replaceAll("^```(json)?", "")
//                    .replaceAll("```$", "")
//                    .trim();
//
//            return new JSONObject(content);
//        } catch (Exception e) {
//            e.printStackTrace();
//            return new JSONObject().put("error", e.getMessage());
//        }
//    }
private JSONObject callChatGPT1(CommentAiDto commentAiDto, List<String> list) {
    String apiKey = "sk-v4yzSqtbttHco6e7wskObkfPhqAYan671q1KjRcS0BAbnV8f"; // 安全起见建议放在配置文件里
    String url = "https://xiaoai.plus/v1/chat/completions";
    try {
        String prompt = """
                你是一个专门分析帖子的一个小助手，我将传一个dto对象以及一个String集合给你 请以管理员的身份分析一下这篇帖子是好是坏
                    以下是它每个字段的含义
                    -content：内容
                    不需要分析这个-touxiang：头像
                    thumbsUp：点赞数
                    thumbsDown：拉踩数
                    replyCount：回复数
                    list集合当中放置的是该帖子下的评论
                    如果你能读取到list集合里面的东西 请把它打印出来
                    主要对他的评论进行分析
            现在用户输入：""" + commentAiDto+list;

        // 构建请求体
        JSONObject message = new JSONObject();
        message.put("role", "user");
        message.put("content", prompt);

        JSONObject body = new JSONObject();
        body.put("model", "gpt-4");
        body.put("messages", new org.json.JSONArray().put(message));

        // 构建请求
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("Authorization", "Bearer " + apiKey)
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body.toString()))
                .build();

        // 发送请求
        HttpClient client = HttpClient.newHttpClient();
        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

        // 输出原始结果供调试
        System.out.println("==[AI Response]==");
        System.out.println(response.body());

        // 检查是否有错误信息
        JSONObject responseJson = new JSONObject(response.body());
        if (responseJson.has("error")) {
            return new JSONObject().put("error", responseJson.getJSONObject("error").getString("message"));
        }

        // 尝试获取 "choices" 数组并解析
        if (responseJson.has("choices")) {
            JSONArray choices = responseJson.getJSONArray("choices");
            String content = choices.getJSONObject(0).getJSONObject("message").getString("content").trim();

            // 清洗返回值内容（去除 JSON 格式的包裹符）
            if (content.startsWith("```")) {
                content = content.replaceAll("```json", "").replaceAll("```", "").trim();
            }

            // 返回解析后的内容
            return new JSONObject().put("content", content);
        } else {
            return new JSONObject().put("error", "响应中未找到 'choices' 字段");
        }

    } catch (Exception e) {
        e.printStackTrace();
        return new JSONObject().put("error", "请求处理失败: " + e.getMessage());
    }
}



}
