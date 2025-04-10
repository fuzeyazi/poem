package com.fuze.potryservice.controller.admin;

import cn.hutool.captcha.CaptchaUtil;
import cn.hutool.captcha.LineCaptcha;
import cn.hutool.http.ContentType;
import cn.hutool.json.JSONObject;
import com.baomidou.mybatisplus.core.toolkit.StringUtils;
import com.fuze.constant.JwtClaimsConstant;
import com.fuze.dto.AdminDto;
import com.fuze.dto.AdminLoginDto;
import com.fuze.entity.Admin;
import com.fuze.potryservice.Aspect.AutoLog;
import com.fuze.potryservice.service.AdminService;
import com.fuze.properties.JwtProperties;
import com.fuze.result.PageResult;
import com.fuze.result.Result;
import com.fuze.utils.JwtUtil;
import com.fuze.utils.RedisUtil;
import com.fuze.vo.AdminLoginVo;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import jakarta.mail.MessagingException;
import jakarta.servlet.ServletOutputStream;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.lang.ObjectUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.io.UnsupportedEncodingException;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/admin")
@Api(tags = "管理的相关接口")
@Slf4j
public class AdminController {

    @Autowired
    private RedisUtil redisUtil;
@Autowired
    private AdminService adminService;
    @Autowired
    private JwtProperties jwtProperties;

    /**
     * 管理员登录接口
     */
    @PostMapping("/login")
    public Result<AdminLoginVo> adminLogin(@RequestBody AdminLoginDto adminLoginDto,
                                         HttpServletResponse resp) {
        log.info("管理员登录");
        JSONObject result = new JSONObject();
        try {
            // 1. 验证验证码
            String redisCode = (String) redisUtil.get(adminLoginDto.getCodeKey());
            log.info("redisCode:{}", redisCode);
            if (StringUtils.isEmpty(adminLoginDto.getCode()) || StringUtils.isEmpty(redisCode) || !adminLoginDto.getCode().equals(redisCode)) {
                result.put("error_description", "验证码错误");
                result.put("error", "invalid_grant");
                resp.setStatus(400);
                redisUtil.del(adminLoginDto.getCodeKey()); // 删除 Redis 中的验证码
                return Result.error("验证码错误");
            }

            // 2. 验证账号密码
            Admin isAuthenticated = adminService.login(adminLoginDto);
            if (isAuthenticated == null) {
                result.put("error_description", "用户名或密码错误");
                result.put("error", "invalid_grant");
                resp.setStatus(400);
                return Result.error("用户名或密码错误");
            }
            // 4. 返回成功结果
            //登录成功后，生成jwt令牌
            Map<String, Object> claims = new HashMap<>();
            claims.put(JwtClaimsConstant.USER_ID, isAuthenticated.getId());
            String token = JwtUtil.createJWT(
                    jwtProperties.getAdminSecretKey(),
                    jwtProperties.getAdminTtl(),
                    claims);
            //封装成vo返回前端
            AdminLoginVo adminLoginVo = AdminLoginVo.builder()
                    .id(isAuthenticated.getId())
                    .userName(isAuthenticated.getUsername())
                    .token(token)
                    .build();
            return Result.success(adminLoginVo);
        } catch (Exception e) {
            log.error("登录接口错误, 错误信息:{}", e.getMessage(), e);
            return Result.error("系统错误");
        }
    }

    /**
     * 获取图片验证码接口
     */
    @ApiOperation("获取验证码接口")
    @RequestMapping("/getCode")
    public Result getCode(HttpServletRequest request, HttpServletResponse response) {
        Map<String, String> result = new HashMap<>();
        try {
            // 定义图片大小
            LineCaptcha captcha = CaptchaUtil.createLineCaptcha(200, 100, 4, 300);
            response.setContentType("image/jpeg");
            response.setHeader("Pragma", "No-cache");

            String imageBase64 = "data:image/png;base64," + captcha.getImageBase64();
            String code = captcha.getCode();
            log.info("生成的图片验证码:{}", code);

            String codeKey = UUID.randomUUID().toString();
            redisUtil.set(codeKey, captcha.getCode());

            result.put("code", imageBase64);
            result.put("codeKey", codeKey);
        } catch (Exception e) {
            log.error("生成图片验证码异常", e);
            return Result.error("生成图片验证码异常");
        }
        return Result.success(result);
    }
    @ApiOperation("发送邮箱验证码进行注册")
    @PostMapping("/register")
    public Result register(@RequestBody AdminDto adminDto) {
        log.info("注册");
        try {
            adminService.register(adminDto);
            return Result.success("注册成功");
        } catch (Exception e) {
            log.error("注册失败", e);
            return Result.error("注册失败");
        }
    }
    @ApiOperation(value = "发送验证码并且保证到验证码")
    @PostMapping("/login/code")
    public Result<String> sendcode(@RequestParam String phone, HttpSession session) throws UnsupportedEncodingException, MessagingException {
        String code=adminService.sendcode(phone,session,1);
        return Result.success(code);
    }
    @ApiOperation("更改用户账号权限")
    @PostMapping("/disable/{status}")
    @AutoLog("更改用户账号权限")
    public Result<String> disable(@PathVariable Integer status,Integer id) {
        log.info("启用禁用用户账号{}", status,id);
            adminService.disable(status,id);
            return Result.success();
    }
    @ApiOperation("分页展示所有用户")
    @GetMapping("/getAll")
    public Result<PageResult> GetLog(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize
    ) {
        PageResult pageInfo = adminService.GetUser(pageNum, pageSize);
        return Result.success(pageInfo);
    }
}
