package com.fuze.potryservice.service.impl;

import cn.hutool.core.util.RandomUtil;
import com.fuze.constant.JwtClaimsConstant;
import com.fuze.constant.MessageConstant;
import com.fuze.dto.*;
import com.fuze.entity.RhesisDataVo;
import com.fuze.entity.UserBook;
import com.fuze.entity.UserJo;
import com.fuze.exception.AccountNotFoundException;
import com.fuze.potryservice.mapper.UserMapper;
import com.fuze.potryservice.service.UserService;

import com.fuze.properties.JwtProperties;
import com.fuze.utils.AliOssUtil;
import com.fuze.utils.JwtUtil;
import com.fuze.utils.PlayerUtil;
import com.fuze.vo.PlanDataVo;
import com.fuze.vo.PoemDataVo;
import com.fuze.vo.PoemLunTanCommentVo;
import com.fuze.vo.TodayReviewVo;
import com.fuze.vo.UserVo;
import jakarta.annotation.Resource;
import jakarta.mail.MessagingException;
import jakarta.mail.internet.MimeMessage;
import jakarta.servlet.http.HttpSession;
import org.eclipse.angus.mail.smtp.SMTPSendFailedException;
import org.mybatis.logging.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;

import java.io.UnsupportedEncodingException;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.temporal.ChronoUnit;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.concurrent.TimeUnit;
import java.util.logging.Logger;

@Service
public class UserServiceimpl implements UserService {
@Autowired
private  UserMapper userMapper;
@Autowired
private JavaMailSender javaMailSender;
@Autowired
private RedisTemplate<String,String> redisTemplate;
    @Autowired
    private AliOssUtil aliOssUtil;
    @Autowired
    private JwtProperties jwtProperties;
    @Autowired
    @Qualifier("mailThreadPool")
    private Executor mailExecutor;
    private final BCryptPasswordEncoder passwordEncoder = new BCryptPasswordEncoder();

    @Override
    public UserJo login1(UserLoginDto userLoginDto) {
        String username = userLoginDto.getUsername();
        String password = userLoginDto.getPassword();
        System.out.println(password);
         UserJo userJo = userMapper.loginbyusername1(username);
//        System.out.println(userJo);
        if(userJo ==null){
            throw new AccountNotFoundException(MessageConstant.ACCOUNT_NOT_FOUND);
        }
        if(userJo.getPassword() == null){
            throw new AccountNotFoundException("该账号未设置密码，请使用邮箱验证码登录");
        }
        if(!passwordEncoder.matches(password, userJo.getPassword())){
            throw new AccountNotFoundException(MessageConstant.PASSWORD_ERROR);
        }
         if(userJo.getStatus()==0){
             throw new AccountNotFoundException(MessageConstant.ACCOUNT_LOCKED);
         }
      return userJo;
  }

    @Override
    public UserJo getByUsername(String username) {
        return userMapper.getbynamme(username);
    }

    @Override
    public void adduser(UserJo newuser) throws Exception {
        String password = newuser.getPassword();
        if (password != null && !password.startsWith("$2a$")) {
            newuser.setPassword(passwordEncoder.encode(password));
        }
        userMapper.adduser(newuser);
    }

    @Override
    public String getopid(int id) {
        return userMapper.getopid(id);
    }

    @Override
    public String getroleid(String name) {
        return userMapper.getroleid(name);
    }

    @Override
    public String ischaid(String name) {
        return userMapper.ischaid(name);
    }

    @Override
    public void deleteCharacter(String name) {
        userMapper.deleteCharacter(name);
    }

    @Override
    public void insertchatId(String chatId) {
        userMapper.insertchatId(chatId);
    }

    @Override
    public void updachatId(String chatId, String roleid) {
        userMapper.updachatId(chatId,roleid);
    }

    @Override
    public UserLogin getmassagebyID(Integer id) {
        return userMapper.getmassagebyID(id);
    }

    @Override
    public void updatemessagebyid(UserLogin userLogin) {
     String touxiang = userLogin.getTouxiang();
     String url=aliOssUtil.upload(touxiang.getBytes(),"user/"+UUID.randomUUID()+".jpg");
     userLogin.setTouxiang(url);
     userMapper.updatemessagebyid213(userLogin);
    }

    @Override
    public void addPoem(UserCollectionPoemDto userCollectionPoemDto) {
        userMapper.addPoem(userCollectionPoemDto);
    }

    @Override
    public void deletePoem(UserCollectionPoemDto userCollectionPoemDto) {
        userMapper.deletepoem(userCollectionPoemDto);
    }

    @Override
    public List<PoemDataVo> getCollect(Integer id) {
        return userMapper.getcollecterct(id);
    }

    @Override
    public List<Integer> getCollectIds(Integer id) {
        return userMapper.getCollectIds(id);
    }

    @Override
    public void addrhesis(UserCollectionRhesisDto userCollectionRhesisDto) {
        userMapper.addrhesis(userCollectionRhesisDto);
    }

    @Override
    public void deletethesis(UserCollectionRhesisDto userCollectionRhesisDto) {
        userMapper.deletehesis(userCollectionRhesisDto);
    }

    @Override
    public List<Integer> getCollectResis(Integer id) {
        return userMapper.getCollectResis(id);
    }

    @Override
    public List<RhesisDataVo> getCollectRhesis(Integer id) {
        return userMapper.getCollectRhesis(id);
    }

    @Override
    public String gettouxiangbyid(Integer userid) {
        return userMapper.gettouxiangbyid(userid);
    }

    @Override
    public String getusernamebyid(Integer userid) {
        return userMapper.getusernamebyid(userid);
    }

    @Override
    public String sendcode(String email, HttpSession session,Integer status) throws UnsupportedEncodingException, MessagingException {
        if(!isValidEmail(email)) {
            throw new AccountNotFoundException("邮箱格式不正确");
        }
        //发送限流：同一邮箱60秒内只允许发一次，防止接口被刷造成邮件轰炸
        Boolean first = redisTemplate.opsForValue().setIfAbsent("login:code:limit:" + email, "1", 60, TimeUnit.SECONDS);
        if(Boolean.FALSE.equals(first)){
            throw new AccountNotFoundException("发送过于频繁，请1分钟后再试");
        }
        String code = RandomUtil.randomNumbers(6);
        //先同步写入Redis（微秒级），再异步发邮件：SMTP耗时不再阻塞请求线程
        redisTemplate.opsForValue().set("login:code:" + email, code, 10, TimeUnit.MINUTES);
        CompletableFuture.runAsync(() -> {
            try {
                MimeMessage message = javaMailSender.createMimeMessage();
                MimeMessageHelper helper = new MimeMessageHelper(message, false);
                helper.setFrom("347185605@qq.com", "古韵传习堂");
                helper.setTo(email);
                helper.setSubject("古韵传习堂验证码");
                helper.setText("<p>古韵传习堂：" +
                                "</p><p>您的验证码是：<strong>" + code + "</strong></p>"
                        , true);
                javaMailSender.send(message);
            } catch (Exception e) {
                System.err.println("验证码邮件异步发送失败: " + email + " - " + e.getMessage());
            }
        }, mailExecutor);
        return "success";
    }

    @Override
    public String loginEmal(UserLoginEmalDto userLoginEmalDto) {
        //判断邮箱是否错误
        if(!isValidEmail(userLoginEmalDto.getEmail())){
            throw new AccountNotFoundException("邮箱错误");
        }
        //判断验证码（rediscode为空说明未发送或已过期；比较方向避免code为null时NPE）
        String code = userLoginEmalDto.getCode();
        String rediscode= redisTemplate.opsForValue().get("login:code:"+userLoginEmalDto.getEmail());
        if(rediscode == null || !rediscode.equals(code)){
            throw new AccountNotFoundException("验证码错误或已过期");
        }
        //验证码一次性消费：校验通过立即作废，有效期内不可重放
        redisTemplate.delete("login:code:" + userLoginEmalDto.getEmail());
        //判断用户是否存在
       UserJo userJo =userMapper.findByEmail(userLoginEmalDto.getEmail());
        //如果不存在新建一个用户（验证码登录用户不设密码，走密码登录会被拦截提示）
        if(userJo==null){
            UserJo newuser = new UserJo();
            newuser.setUsername(userLoginEmalDto.getEmail());
            newuser.setEmail(userLoginEmalDto.getEmail());
            newuser.setDegree("小学");
            newuser.setTouxiang("https://webxiangmu.oss-cn-beijing.aliyuncs.com/lun/40e10c38-4470-4832-be75-67af2861e0e1.png");
            newuser.setCreatetime(LocalDate.now().toString());
            newuser.setName("不吃香菜"+"（哈基米版#"+ UUID.randomUUID().toString().substring(0, 6)+")");
            userMapper.adduser(newuser);
            Integer id=userMapper.findidbyemail(userLoginEmalDto.getEmail());
            Map<String, Object> claims = new HashMap<>();
            claims.put(JwtClaimsConstant.USER_ID, id);
            claims.put(JwtClaimsConstant.Dagerr, 1L);
            return JwtUtil.createJWT(jwtProperties.getUserSecretKey(), jwtProperties.getUserTtl(), claims);
        }else {
            Map<String, Object> claims = new HashMap<>();
            claims.put(JwtClaimsConstant.USER_ID, userJo.getId());
            claims.put(JwtClaimsConstant.Dagerr, degreeToNum(userJo.getDegree()));
            return JwtUtil.createJWT(jwtProperties.getUserSecretKey(), jwtProperties.getUserTtl(), claims);
        }
    }

    private Long degreeToNum(String degree){
        if("小学".equals(degree)) return 1L;
        if("初中".equals(degree)) return 2L;
        if("高中".equals(degree)) return 3L;
        return 4L;
    }
    @Override
    public boolean findPoem(UserCollectionPoemDto userCollectionPoemDto) {
        if(userMapper.findPoem(userCollectionPoemDto)==null){
            return false;
        }
        return true;
    }



    @Override
    public String updatepassword(UserLoginEmalDto userLoginEmalDto) {
        if(!isValidEmail(userLoginEmalDto.getEmail())){
            throw new AccountNotFoundException("邮箱错误");
        }
        if(userMapper.findByEmail(userLoginEmalDto.getEmail())==null){
            return "邮箱不存在";
        }
        //判断验证码
        String code = userLoginEmalDto.getCode();
        String rediscode= redisTemplate.opsForValue().get("login:code:"+userLoginEmalDto.getEmail());
        if(rediscode == null || !rediscode.equals(code)){
            return "验证码错误或已过期";
        }
        //验证码一次性消费
        redisTemplate.delete("login:code:" + userLoginEmalDto.getEmail());
       String oldPassword = userMapper.getpassword(userLoginEmalDto.getEmail());
        if(passwordEncoder.matches(userLoginEmalDto.getPassword(), oldPassword)){
           return "新密码不能与旧密码相同";
       }
       userLoginEmalDto.setPassword(passwordEncoder.encode(userLoginEmalDto.getPassword()));
      userMapper.updatemessagebyid1(userLoginEmalDto);
       return "修改成功";
    }

    @Override
    public void adduserbook1(UserBook userBook, Long dagree) {
        String degreeText = dagree1(dagree);   //数字→文案:1小学 2初中 3高中 其他成年人
        List<Integer> keys = userMapper.getpoemidbydagree(degreeText);
        userMapper.adduserbook(userBook);      //book_id自增回填
        //修复断链:原实现查询结果keys被丢弃,建的是一本空书
        if (keys != null && !keys.isEmpty()) {
            userMapper.addBookPoemsBatch(userBook.getBookid(), keys);
            userMapper.updateBookSum(userBook.getBookid(), keys.size());
        }
    }

    @Override
    public void adduserbook(UserBook userBook) {
        if (userBook.getBookname() == null || userBook.getBookname().isBlank()) {
            throw new com.fuze.exception.BaseException("请填写诗集名");   // 原先放行NULL书名(前端绕过时库里留死书)
        }
        userMapper.adduserbook(userBook);
    }

    @Override
    public void addPoemword(UserBookPoemDto userBookPoemDto) {
        userBookPoemDto.setLastReviewDate(LocalDate.now());
        userBookPoemDto.setReviewCount(0);
        Integer exists = userMapper.findPoembybookid1(userBookPoemDto);
        if (exists != null && exists > 0) {
            return;   // 已在书中,幂等跳过
        }
        userMapper.addPoemword(userBookPoemDto);
        userMapper.updatePowmWord(userBookPoemDto.getBookid());
    }

    @Override
    public List<UserBook> show(Integer idd) {
        return userMapper.show(idd);
    }

    @Override
    public List<PoemDataVo> showpoem(Integer bookid) {
      List<Integer> keys = userMapper.getpoemidbybookid(bookid);
      // 空书防御: 空列表进foreach会生成"id in"断SQL(新建诗集点开即500)
      if (keys == null || keys.isEmpty()) {
          return java.util.Collections.emptyList();
      }
      return userMapper.showpoem(keys);
    }

    @Override
    public Map<String, Integer> getForgetCurve(Integer userId) {
        // 查询用户所有复习记录
        List<UserBookPoemDto> poems = userMapper.findByUserid(userId);

        // 初始化时间段和数据
        Map<String, Integer> forgetCurveData = new HashMap<>();
        forgetCurveData.put("1天", 0);
        forgetCurveData.put("3天", 0);
        forgetCurveData.put("7天", 0);
        forgetCurveData.put("14天", 0);
        forgetCurveData.put("30天", 0);

        // 计算复习间隔并分组
        for (UserBookPoemDto poem : poems) {
            LocalDate lastReviewDate = poem.getLastReviewDate();
            LocalDate now = LocalDate.now();
            long daysBetween = ChronoUnit.DAYS.between(lastReviewDate, now);

            if (daysBetween <= 1) {
                forgetCurveData.put("1天", forgetCurveData.get("1天") + 1);
            } else if (daysBetween <= 3) {
                forgetCurveData.put("3天", forgetCurveData.get("3天") + 1);
            } else if (daysBetween <= 7) {
                forgetCurveData.put("7天", forgetCurveData.get("7天") + 1);
            } else if (daysBetween <= 14) {
                forgetCurveData.put("14天", forgetCurveData.get("14天") + 1);
            } else if (daysBetween <= 30) {
                forgetCurveData.put("30天", forgetCurveData.get("30天") + 1);
            }
        }

        return forgetCurveData;
    }
    List<Integer> reviewIntervals = Arrays.asList(1, 2, 4, 7, 15);
    @Override
    public void createReviewPlan1(Integer userId, Integer bookId) {
        LocalDate today = LocalDate.now();
        for(Integer interval : reviewIntervals){
            LocalDate reviewDate = today.plusDays(interval);
            UserBookPoemDto userBookPoemDto = new UserBookPoemDto();

        }
    }

    @Override
    public void start(UserBook userBook, Integer id) {
        int sum=userMapper.getsum(userBook.getBookid(),id);
    }

    @Override
    public void start1(Integer bookId, Integer id, Integer much) {
        int m = (much == null || much <= 0) ? 5 : much;
        //批量化:一条SQL按id序每m首一组排期(原为N次循环单行UPDATE)
        userMapper.scheduleBatch(bookId, m, LocalDateTime.now());
    }

    @Override
    public Integer dueReviewCount() {
        Long uid = com.fuze.context.BaseContext.getCurrentId();
        Integer c = userMapper.GetDueReviewCount(uid);
        return c == null ? 0 : c;
    }

    @Override
    public List<TodayReviewVo> todayReviews(Integer bookid) {
        return userMapper.getTodayReviews(bookid);
    }

    /**
     * 复习曲线数据(按日聚合): 原select *映射PlanDataVo(聚合语义VO)列全不匹配→NPE,
     * 曲线图接口自上线即500。重写: 基于userbookpoem按nextReviewDate/lastReviewDate聚合——
     * sum=每日计划(新学+复习)首数, time=该日各诗的复习时间点(小时), isReview=该日是否已发生。
     * 返回按日期升序, 覆盖今天起至未来全部计划。
     */
    @Override
    public List<PlanDataVo> showplan(Integer bookid) {
        List<UserBookPoemDto> rows = userMapper.getBookPoemRows(bookid);
        Map<LocalDate, List<UserBookPoemDto>> byDay = new java.util.TreeMap<>();
        LocalDate today = LocalDate.now();
        for (UserBookPoemDto r : rows) {
            LocalDate learned = r.getLastReviewDate();
            LocalDate next = r.getNextReviewDate();
            // 新学日: 学习当天计入
            if (learned != null) {
                byDay.computeIfAbsent(learned, k -> new ArrayList<>()).add(r);
            }
            // 复习日: nextReviewDate(未来计划或已复习日)
            if (next != null) {
                byDay.computeIfAbsent(next, k -> new ArrayList<>()).add(r);
            }
        }
        List<PlanDataVo> out = new ArrayList<>();
        for (Map.Entry<LocalDate, List<UserBookPoemDto>> e : byDay.entrySet()) {
            PlanDataVo vo = new PlanDataVo();
            vo.setDate(java.sql.Date.valueOf(e.getKey()));
            vo.setSum(e.getValue().stream().map(UserBookPoemDto::getPoemid).distinct().toList());
            // 已复习判定: lastReviewDate>=该日 且 reviewCount>0 的诗; 复习时间取当日各诗学习时刻(小时)
            boolean done = e.getKey().isBefore(today) || e.getKey().equals(today);
            vo.setIsReview(e.getValue().stream()
                    .map(r -> (done && r.getReviewCount() != null && r.getReviewCount() > 0) ? 1 : 0)
                    .toList());
            vo.setTime(e.getValue().stream()
                    .map(r -> done && r.getLastReviewDate() != null
                            ? java.time.LocalTime.of(9, 0) : null)
                    .toList());
            out.add(vo);
        }
        return out;
    }

    @Override
    public List<PoemLunTanCommentVo> selectcomment(Integer id) {
        return userMapper.selectcomment(id);
    }

    @Override
    public void deleteComment(Integer commentid) {
        userMapper.deleteComment(commentid);
    }

    @Override
    public UserJo login11(UserLoginEmalDtoPlus userLoginEmalDtoPlus) {
        String username = userLoginEmalDtoPlus.getEmail();
        UserJo userJo = userMapper.loginbyusername1(username);
        return userJo;
    }

    private  String dagree1(Long dagree){
        if(dagree==1){
            return "小学";
        }
        if(dagree==2){
            return "初中";
        }
        if(dagree==3){
            return "高中";
        }
        return "成年人";
   }

    private boolean isValidEmail(String email) {
        // 简化的邮箱正则表达式
        String emailRegex = "^[a-zA-Z0-9_+&*-]+(?:\\.[a-zA-Z0-9_+&*-]+)*@(?:[a-zA-Z0-9-]+\\.)+[a-zA-Z]{2,7}$";
        return email.matches(emailRegex);
    }
}
