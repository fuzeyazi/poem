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
import com.fuze.vo.UserVo;
import jakarta.annotation.Resource;
import jakarta.mail.MessagingException;
import jakarta.mail.internet.MimeMessage;
import jakarta.servlet.http.HttpSession;
import org.eclipse.angus.mail.smtp.SMTPSendFailedException;
import org.mybatis.logging.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.stereotype.Service;

import java.io.UnsupportedEncodingException;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.temporal.ChronoUnit;
import java.util.*;
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
    private static final String hostUrl = "https://ai-character.xfyun.cn/api";
    private static final String appId =  "4b88e2d9";
    private static final String secret = "NDJkYWVjOTk2ODg5N2ExMDIyMWJkNGNm";
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
        //mp5加密
//           password= DigestUtils.md5DigestAsHex(password.getBytes());
         if(!password.equals(userJo.getPassword())){
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
        PlayerUtil playerUtil = new PlayerUtil();
        String username=newuser.getUsername();
        //检测是否玩家是否已经注册
        playerUtil.ifRegister(hostUrl,appId,secret,username);
        //注册玩家，这边我们是直接让注册的用户就为玩家id
        String playerId = playerUtil.register(hostUrl,appId,secret,username,"古风","都是哈急人");
        newuser.setOpenid(playerId);
        System.out.println(playerId);
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
     userMapper.updatemessagebyid(userLogin);
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
        //校验手机号
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
                  redisTemplate.opsForValue().set("login:code:" + email, code, 10, TimeUnit.MINUTES);
              }else {
                  helper.setSubject("");
                  helper.setText("<p>古韵传习堂：" +
                                  "</p><p>您的验证码是：<strong>" + code + "</strong></p>"
                          , true);
                  // 发送
                  javaMailSender.send(message);
                  // 将验证码存入redis,并且设置有效期1分钟
                  redisTemplate.opsForValue().set("login:code:" + email, code, 10, TimeUnit.MINUTES);
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
    public String loginEmal(UserLoginEmalDto userLoginEmalDto) {
        //判断邮箱是否错误
        if(!isValidEmail(userLoginEmalDto.getEmail())){
            throw new AccountNotFoundException("邮箱错误");
        }
        //判断验证码
        String code = userLoginEmalDto.getCode();
        String rediscode= redisTemplate.opsForValue().get("login:code:"+userLoginEmalDto.getEmail());
        if(!code.equals(rediscode)){
            return "验证码错误";
        }
        //判断用户是否存在
       UserJo userJo =userMapper.findByEmail(userLoginEmalDto.getEmail());
        //如果不存在新建一个用户
        if(userJo==null){
            UserJo newuser = new UserJo();
            newuser.setUsername(userLoginEmalDto.getEmail());
            //默认密码
            newuser.setPassword("123456");
            newuser.setEmail(userLoginEmalDto.getEmail());
            newuser.setDegree("小学");
            userMapper.adduser(newuser);
            Integer id=userMapper.findidbyemail(userLoginEmalDto.getEmail());
            Map<String, Object> claims = new HashMap<>();
            claims.put(JwtClaimsConstant.USER_ID, id);
            String token = JwtUtil.createJWT(jwtProperties.getUserSecretKey(), jwtProperties.getUserTtl(), claims);
            return token;
        }else {
            Map<String, Object> claims = new HashMap<>();
            claims.put(JwtClaimsConstant.USER_ID, userJo.getId());
            String token = JwtUtil.createJWT(jwtProperties.getUserSecretKey(), jwtProperties.getUserTtl(), claims);
            return token;
        }
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
        if(!code.equals(rediscode)){
            return "验证码错误";
        }
       if(Objects.equals(userLoginEmalDto.getPassword(), userMapper.getpassword(userLoginEmalDto.getEmail()))){
           return "新密码不能与旧密码相同";
       }
      userMapper.updatemessagebyid1(userLoginEmalDto);
       return "修改成功";
    }

    @Override
    public void adduserbook1(UserBook userBook, Long dagree) {
        String dagree1=dagree1(dagree);
        List<Integer> keys = userMapper.getpoemidbydagree(dagree1);
        userMapper.adduserbook11(userBook,keys);
    }

    @Override
    public void adduserbook(UserBook userBook) {
        userMapper.adduserbook(userBook);
    }

    @Override
    public void addPoemword(UserBookPoemDto userBookPoemDto) {
        userBookPoemDto.setLastReviewDate(LocalDate.now());
        userBookPoemDto.setReviewCount(0);
        if(userMapper.findPoembybookid1(userBookPoemDto)){
            return;
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
        int sum = userMapper.getsum(bookId, id);
        LocalDateTime zz = LocalDateTime.now();

        List<Integer> pomeid = userMapper.getpoemidbybookid(bookId);
        for (int i = 0; i <sum; i++) {
           userMapper.updatatep1(bookId, pomeid.get(i), zz,pomeid.get(i));
            if ((i) % much == 0&&i!=0) {
                zz = zz.plusDays(1);
            }
        }
    }

    @Override
    public List<PlanDataVo> showplan(Integer bookid) {
        List<PlanDataVo> planDataVos = userMapper.showplan(bookid);
        for(PlanDataVo planDataVo:planDataVos){
            List<LocalTime> time=planDataVo.getTime();
            List<Integer> isReview=planDataVo.getIsReview();
            for(int i=0;i<time.size();i++){
                if(isReview.get(i)==1){
                    time.set(i,null);
                }
            }
        }
        return planDataVos;
    }

    @Override
    public List<PoemLunTanCommentVo> selectcomment(Integer id) {
        return userMapper.selectcomment(id);
    }

    @Override
    public void deleteComment(Integer commentid) {
        userMapper.deleteComment(commentid);
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
