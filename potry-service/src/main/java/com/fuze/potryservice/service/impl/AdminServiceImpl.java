package com.fuze.potryservice.service.impl;

import com.fuze.potryservice.cache.MultiLevelCacheManager;
import cn.hutool.core.util.RandomUtil;
import com.fuze.constant.MessageConstant;
import com.fuze.constant.StatusConstant;
import com.fuze.dto.AdminDto;
import com.fuze.dto.AdminLoginDto;
import com.fuze.dto.PotryDTO;
import com.fuze.dto.RhesisDto;
import com.fuze.entity.*;
import com.fuze.exception.AccountLockedException;
import com.fuze.exception.AccountNotFoundException;
import com.fuze.exception.PasswordErrorException;
import com.fuze.potryservice.mapper.AdminMapper;
import com.fuze.potryservice.mapper.UserMapper;
import com.fuze.potryservice.service.AdminService;
import com.fuze.result.PageResult;
import com.fuze.vo.*;
import com.github.pagehelper.Page;
import com.github.pagehelper.PageHelper;
import com.github.pagehelper.PageInfo;
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
    private MultiLevelCacheManager multiLevelCacheManager;
    /** BCrypt自适应哈希(默认强度10,自带随机盐,同一密码每次哈希结果不同) */
    private final org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder passwordEncoder =
            new org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder();
    @Autowired
    private org.springframework.mail.javamail.JavaMailSender javaMailSender;
    @Autowired
    private org.springframework.data.redis.core.StringRedisTemplate redisTemplate;
    @Autowired
    private UserMapper userMapper;

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
        String stored = result.getPassword();
        boolean matched;
        if (stored != null && stored.startsWith("$2")) {
            // 已是BCrypt($2a$前缀),直接校验
            matched = passwordEncoder.matches(password, stored);
        } else {
            // 存量MD5: 校验通过后立即原位升级为BCrypt —— 零停机平滑迁移,
            // 存量账号逐个在下次成功登录时切换,无需批量重置
            matched = stored != null
                    && stored.equalsIgnoreCase(DigestUtils.md5DigestAsHex(password.getBytes()));
            if (matched) {
                adminMapper.updatePassword(result.getId(), passwordEncoder.encode(password));
                log.info("管理员密码已原位升级为BCrypt: id={}", result.getId());
            }
        }
        if (!matched) {
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
        String title = potryDTO.getTitle();
        String dynasty = potryDTO.getDynasty();
        String writer = potryDTO.getWriter();
        Poem poem = adminMapper.getbyTitleAnd(title,dynasty,writer);
        if(poem == null) {
            adminMapper.insert(potryDTO);
        }else
        {
            throw new RuntimeException("古诗已存在");
        }
    }
    @Override
    public void delete(List<Long> ids) {
        if (ids != null) {
            for (Long id : ids) {
                adminMapper.delete(id);
                multiLevelCacheManager.evictPoem(id);
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
            admin.setPassword(passwordEncoder.encode(adminDto.getPassword()));
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
        if (potryDTO != null && potryDTO.getId() > 0) {
            multiLevelCacheManager.evictPoem((long) potryDTO.getId());
        }
    }

    @Override
    public void disable(Integer status ,Integer id) {
        UserJo userJo = UserJo.builder()
                .status(status)
                .id(id)
                .build();
        userMapper.update(userJo);
    }

    @Override
    public List<PotryDTO> GetContent(PotryDTO potryDTO) {
        List<PotryDTO> list = adminMapper.GetContent(potryDTO);
        log.info("模糊查询古诗执行:"+list);
        return list;
    }

    @Override
    public void deleteByTitle(String title) {
        adminMapper.deleteByTitle(title);
    }

    @Override
    public void save(Suggestion suggestion) {
        adminMapper.save(suggestion);
    }

    @Override
    public PageResult GetUser(Integer pageNum, Integer pageSize) {
        PageHelper.startPage(pageNum, pageSize);
        Page<UserTotalVo> page = adminMapper.GetUser();
        long total = page.getTotal();
        List<UserTotalVo> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public PageResult GetPoem(Integer pageNum, Integer pageSize) {
        PageHelper.startPage(pageNum, pageSize);
        Page<PoemDataVo> page = adminMapper.GetPoem();
        long total = page.getTotal();
        List<PoemDataVo> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public PageResult GetBlog(Integer pageNum, Integer pageSize) {
        PageHelper.startPage(pageNum, pageSize);
        Page<BlogVO> page = adminMapper.GetBlog();
        long total = page.getTotal();
        List<BlogVO> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public void deleteBlogById(List<Integer> ids) {
        for(Integer id : ids)
        {
            adminMapper.deleteBlogById(id);
        }
    }

    @Override
    public PageResult GetAllRhesis(Integer pageNum, Integer pageSize) {
        PageHelper.startPage(pageNum, pageSize);
        Page<Rhesis> page = adminMapper.GetRhesis();
        long total = page.getTotal();
        List<Rhesis> records = page.getResult();
        return new PageResult(total, records);
    }

    @Override
    public void deleteRhesisById(List<Integer> ids) {
        for(Integer id : ids)
        {
            adminMapper.deleteRhesisById(id);
        }
    }

    @Override
    public void addRhesis(RhesisDto rhesisDto) {
        adminMapper.addRhesis(rhesisDto);
    }

    @Override
    public void updateRhesis(RhesisDto rhesisDto) {
        adminMapper.updateRhesis(rhesisDto);
    }

    @Override
    public List<RhesisDto> GetRhesisByPoemName(String name) {
        return adminMapper.GetRhesisByPoemName(name);
    }

    @Override
    public Long getUserCount() {
      return adminMapper.getUserCount();
    }

    @Override
    public Long getRhesisCount() {
        return adminMapper.getRhesisCount();
    }
    @Override
    public PageResult GetbyWord(Integer pageNum,
                                Integer pageSize,
                                String word) {
        PageHelper.startPage(pageNum, pageSize);
        Page<PotryDTO> page = adminMapper.Getbyword(word);
        long total = page.getTotal();
        List<PotryDTO> records = page.getResult();
        return new PageResult(total, records);
    }


    private boolean isValidEmail(String email) {
        // 简化的邮箱正则表达式
        String emailRegex = "^[a-zA-Z0-9_+&*-]+(?:\\.[a-zA-Z0-9_+&*-]+)*@(?:[a-zA-Z0-9-]+\\.)+[a-zA-Z]{2,7}$";
        return email.matches(emailRegex);
    }
}
