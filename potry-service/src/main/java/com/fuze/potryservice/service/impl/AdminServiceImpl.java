package com.fuze.potryservice.service.impl;
import cn.hutool.core.util.RandomUtil;
import com.fuze.constant.MessageConstant;
import com.fuze.constant.StatusConstant;
import com.fuze.dto.AdminDto;
import com.fuze.dto.AdminLoginDto;
import com.fuze.dto.PotryDTO;
import com.fuze.entity.Admin;
import com.fuze.exception.AccountLockedException;
import com.fuze.exception.AccountNotFoundException;
import com.fuze.exception.PasswordErrorException;
import com.fuze.potryservice.mapper.AdminMapper;
import com.fuze.potryservice.service.AdminService;
import jakarta.mail.MessagingException;
import jakarta.mail.internet.MimeMessage;
import jakarta.servlet.http.HttpSession;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.stereotype.Service;
import org.springframework.util.DigestUtils;

import java.io.UnsupportedEncodingException;
import java.util.List;
import java.util.concurrent.TimeUnit;

@Service
@Slf4j
public class AdminServiceImpl implements AdminService {

    @Autowired
    private AdminMapper adminMapper;
    @Autowired
    private org.springframework.mail.javamail.JavaMailSender javaMailSender;
    @Autowired
    private org.springframework.data.redis.core.StringRedisTemplate redisTemplate;

    @Override
    public Admin login(AdminLoginDto adminLoginDto) {
        String username = adminLoginDto.getUsername();
        String password = adminLoginDto.getPassword();
//匹配数据库里面的username
        Admin result = adminMapper.getByUsername(username);
//对获取的password进行匹配
        if (result == null) {
            //账号不存在
            throw new AccountNotFoundException(MessageConstant.ACCOUNT_NOT_FOUND);
        }
        password = DigestUtils.md5DigestAsHex(password.getBytes());
        System.out.println(password);
        if (!password.equals(result.getPassword())) {
            //密码错误
            throw new PasswordErrorException(MessageConstant.PASSWORD_ERROR);
        }

        if (result.getStatus() == StatusConstant.DISABLE) {
            //账号被锁定
            throw new AccountLockedException(MessageConstant.ACCOUNT_LOCKED);
        }

        //3、返回实体对象
        return result;

    }
    @Override
    public void add(PotryDTO potryDTO) {
        if(potryDTO.getDynasty()!=null||potryDTO.getTitle()!=null||potryDTO.getWriter()!=null||potryDTO.getContent()!=null)
        {
            adminMapper.insert(potryDTO);
        }
       else {
            throw new RuntimeException("添加失败");
        }
    }
    @Override
    public void delete(List<Long> ids) {
        if(ids!=null)
        {
            for(Long id : ids) {
                adminMapper.delete(id);
            }
        }
        else {
            throw new RuntimeException("删除失败");
        }
    }
    @Override
    public void register(AdminDto adminDto) {
            //判断验证码是否正确
            String code = adminDto.getCode();
            String rediscode = redisTemplate.opsForValue().get("Adminlogin:code:" + adminDto.getEmail());
        log.info("用户输入的验证码: {}, Redis中的验证码: {}", code, rediscode);
            if (!code.equals(rediscode)) {

                throw new RuntimeException("验证码错误");
            }
            Admin admin = new Admin();
            admin.setUsername(adminDto.getUsername());
            admin.setEmail(adminDto.getEmail());
            admin.setPassword(adminDto.getPassword());
            admin.setPassword(DigestUtils.md5DigestAsHex(admin.getPassword().getBytes()));
            //设置默认状态为1
            admin.setStatus(1);
            adminMapper.register(admin);
    }
    @Override
    public String sendcode(String email, HttpSession session, int status) throws UnsupportedEncodingException, MessagingException {
        //校验email
        if(!(adminMapper.getByemail(email)==null)) {
            return "邮箱已被注册";
        }
        if(isValidEmail(email)) {
            //符合，生成验证码
            String code = RandomUtil.randomNumbers(6);
            try {

                MimeMessage message = javaMailSender.createMimeMessage();
                MimeMessageHelper helper = new MimeMessageHelper(message, false);
                helper.setFrom("347185605@qq.com", "古韵传习堂");
                helper.setTo(email);
                if(status==1){
                    helper.setSubject("");
                    helper.setText("<p>古韵传习堂：" +
                                    "</p><p>您的验证码是：<strong>" + code + "</strong></p>"
                            , true);
                    // 发送
                    javaMailSender.send(message);
                    // 将验证码存入redis,并且设置有效期1分钟
                    redisTemplate.opsForValue().set("Adminlogin:code:" + email, code, 10, TimeUnit.MINUTES);
                }else {
                    helper.setSubject("");
                    helper.setText("<p>古韵传习堂：" +
                                    "</p><p>您的验证码是：<strong>" + code + "</strong></p>"
                            , true);
                    // 发送
                    javaMailSender.send(message);
                    // 将验证码存入redis,并且设置有效期1分钟
                    redisTemplate.opsForValue().set("Adminlogin:code:" + email, code, 10, TimeUnit.MINUTES);
                }

            } catch (Exception e) {
                e.printStackTrace();
                return "发送失败，邮箱不存在";
            }
            return code;
        }else {
            return "邮箱格式不正确";
        }
    }

    @Override
    public void update(PotryDTO potryDTO) {
        adminMapper.update(potryDTO);

    }

    private boolean isValidEmail(String email) {
        // 简化的邮箱正则表达式
        String emailRegex = "^[a-zA-Z0-9_+&*-]+(?:\\.[a-zA-Z0-9_+&*-]+)*@(?:[a-zA-Z0-9-]+\\.)+[a-zA-Z]{2,7}$";
        return email.matches(emailRegex);
    }
}
