package com.fuze.potryservice.controller.admin;

import com.fuze.dto.PotryDTO;
import com.fuze.potryservice.Aspect.AutoLog;
import com.fuze.potryservice.service.AdminService;
import com.fuze.potryservice.service.PotryService;
import com.fuze.result.PageResult;
import com.fuze.result.Result;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import com.fuze.utils.JwtUtil;
import com.fuze.properties.JwtProperties;
import com.fuze.constant.JwtClaimsConstant;

import java.util.List;

@RestController("管理端")
@RequestMapping("/admin/potry")
@Api(tags = "诗词管理的相关接口")
@Slf4j
public class PotryController {
    @Autowired
    private  PotryService potryService;
    @Autowired
    private AdminService adminService;
    @Autowired
    private JwtProperties jwtProperties;

    private static final HttpClient HTTP_CLIENT = HttpClient.newBuilder()
            .connectTimeout(java.time.Duration.ofSeconds(10))
            .build();
    @ApiOperation(value = "获取古诗的数量")
    @GetMapping("/GetCount")
    public Result<Integer> GetCount() {
        //直接调用
        log.info("获取现存古诗数量执行:");
        Integer count = potryService.getcount();
        return Result.success(count);
    }
    @ApiOperation(value = "添加古诗")
    @AutoLog(value = "添加古诗")
    @PostMapping("/add")
public Result add(@RequestBody PotryDTO potryDTO) {
        log.info("添加古诗执行:{}",potryDTO);
        adminService.add(potryDTO);
        // MySQL↔Milvus一致性: 导入即同步——异步通知agent做在线增量嵌入(失败不阻塞导入,syncstats对账兜底)
        notifyKbSync("poem:" + potryDTO.getTitle());
        return Result.success("添加成功");
    }

    /**
     * 通知agent增量同步知识库(签名内部admin token调 /api/admin/kb/sync)。
     * 异步执行: 嵌入耗时数十ms/块,不应拖慢导入接口; 失败仅告警,一致性由对账接口与全量重建兜底。
     */
    private void notifyKbSync(String source) {
        CompletableFuture.runAsync(() -> {
            try {
                java.util.HashMap<String, Object> claims = new java.util.HashMap<>();
                claims.put(JwtClaimsConstant.USER_ID, 1);   // jjwt会向claims写exp,必须可变Map
                String token = JwtUtil.createJWT(jwtProperties.getAdminSecretKey(), 60_000, claims);
                HttpRequest req = HttpRequest.newBuilder(
                                URI.create("http://localhost:8000/api/admin/kb/sync?title="
                                        + java.net.URLEncoder.encode(source.substring(5), java.nio.charset.StandardCharsets.UTF_8)))
                        .header("token", token)
                        .timeout(java.time.Duration.ofSeconds(120))
                        .POST(HttpRequest.BodyPublishers.noBody()).build();
                HttpResponse<String> resp = HTTP_CLIENT
                        .send(req, HttpResponse.BodyHandlers.ofString());
                log.info("知识库增量同步完成({}): {} {}", source, resp.statusCode(), resp.body());
            } catch (Exception e) {
                log.warn("agent知识库同步通知失败({}),不阻塞导入;对账兜底: GET /api/admin/kb/syncstats", source, e);
            }
        });
    }
    @ApiOperation(value = "批量删除古诗")
    @AutoLog(value = "删除古诗")
    @PostMapping("/delete")
    public Result delete(@RequestBody List<Long> ids) {
        log.info("批量删除古诗执行:");
        adminService.delete(ids);
        return Result.success("删除成功");
    }
@ApiOperation(value = "修改古诗")
@AutoLog(value = "修改古诗")
    @PostMapping("/update")
    public Result update(@RequestBody PotryDTO potryDTO) {
        log.info("修改古诗执行:");
        adminService.update(potryDTO);
        return Result.success("修改成功");
    }
    @ApiOperation("模糊查询古诗")
    @GetMapping("/getPoem")
    public Result<PageResult> GetLog(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize,
            @RequestParam String word
    ) {
        PageResult pageInfo = adminService.GetbyWord(pageNum, pageSize,word);
        return Result.success(pageInfo);
    }
    @ApiOperation("根据标题删除古诗")
    @PostMapping("/deletePoem")
    public Result deletePoem(String title) { 
        log.info("根据标题删除古诗执行:");
        adminService.deleteByTitle(title);
        return Result.success("删除成功");
    }
    @ApiOperation("分页获取所有古诗")
    @GetMapping("/GetPoemPage")
    public Result<PageResult> GetLog(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize
    ) {
        PageResult pageInfo = adminService.GetPoem(pageNum, pageSize);
        return Result.success(pageInfo);
    }

}
