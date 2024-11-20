package com.fuze.potryservice.controller.user;

import com.fuze.constant.MessageConstant;
import com.fuze.context.BaseContext;
import com.fuze.dto.*;
import com.fuze.entity.RhesisDataVo;
import com.fuze.entity.UserBook;
import com.fuze.entity.UserJo;
import com.fuze.exception.AccountNotFoundException;
import com.fuze.potryservice.service.UserService;
import com.fuze.properties.JwtProperties;
import com.fuze.constant.JwtClaimsConstant;
import com.fuze.result.Result;
import com.fuze.utils.JwtUtil;
import com.fuze.vo.*;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import jakarta.mail.MessagingException;
import jakarta.servlet.http.HttpSession;
import lombok.Value;
import lombok.extern.slf4j.Slf4j;

import org.apache.catalina.User;
import org.springframework.ai.openai.OpenAiAudioSpeechModel;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.util.DigestUtils;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;

import java.io.IOException;
import java.io.UnsupportedEncodingException;
import java.time.LocalDate;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

@RestController
@RequestMapping("/user")
@Api(tags ="用户的相关接口")
@Slf4j

//todo 作者收藏的增删改查
public class UserController {


    //此为角色扮演的api
    private static final String hostUrl = "https://ai-character.xfyun.cn/api";
    private static final String appId =  "4b88e2d9";
    private static final String secret = "NDJkYWVjOTk2ODg5N2ExMDIyMWJkNGNm";
    //
    @Autowired
    private UserService userService;
    @Autowired
    private JwtProperties jwtProperties;
    @Autowired
    private OpenAiAudioSpeechModel openAiAudioSpeechModel;
    @ApiOperation(value = "用户登录")
    @PostMapping("/login")
    public Result<UserVo> login(@RequestBody UserLoginDto userLoginDto) {
        try {
            UserJo user1 = userService.login1(userLoginDto);
            //登录成功后生成jwt令牌
            // 1.生成jwt令牌
            //claims可以接收任何的数据
            Map<String, Object> claims = new HashMap<>();
            claims.put(JwtClaimsConstant.USER_ID, user1.getId());
            String Dagger=user1.getDegree();
            Long degree;
            if(Objects.equals(Dagger, "小学")){
                degree= 1L;
            }else if(Objects.equals(Dagger, "初中")){
                degree= 2L;
            }else if(Objects.equals(Dagger, "高中")){
                degree= 3L;
            }else{
                degree= 4L;
            };
            claims.put(JwtClaimsConstant.Dagerr,degree);
            String token = JwtUtil.createJWT(jwtProperties.getUserSecretKey(), jwtProperties.getUserTtl(), claims);
            UserVo userVo = UserVo.builder()
                    .id(user1.getId())
                    .username(user1.getUsername())
                    .name(user1.getName())
                    .openid(user1.getOpenid())
                    .token(token)
                    .degree(user1.getDegree())
                    .build();
            log.info("用户登录成功，用户id为：" + user1.getId());
            log.info("用户学历为：" + BaseContext.getDagree());
            return Result.success(userVo);
        } catch (Exception e) {
            log.error("Error during user login", e);
            return Result.error("Internal server error");
        }
    }
    @ApiOperation(value = "发送验证码并且保证到验证码")
    @PostMapping("/login/code")
    public Result<String> sendcode(@RequestParam String phone, HttpSession session,@RequestParam int status) throws UnsupportedEncodingException, MessagingException {
     String code=userService.sendcode(phone,session,status);
     return Result.success(code);
    }
@ApiOperation(value = "邮箱登录或者注册")
@PostMapping("/login/email")
public Result<String> login1(@RequestBody UserLoginEmalDto userLoginEmalDto) {
   String token=userService.loginEmal(userLoginEmalDto);
        return Result.success(token);
}


    @ApiOperation("用户注册，而且注册后直接赋予用户ai的角色")
    @PostMapping("/register")
    public Result<String> Register(@RequestBody UserDto userDto) throws Exception {
        String username=userDto.getUsername();
        String password=userDto.getPassword();
        System.out.println(username);
        //查询用户名是否重复
        UserJo userJo = userService.getByUsername(username);
        System.out.println(userJo);
        if(userJo!=null){
            throw new AccountNotFoundException(MessageConstant.ALREADY_EXISTS);
        }
        UserJo newuser=new UserJo();
        userDto.setPassword(password);
        BeanUtils.copyProperties(userDto, newuser);
        userService.adduser(newuser);
        System.out.println(newuser);
        return Result.success();
    }
    @ApiOperation(value = "忘记密码")
    @GetMapping("/forget")
    public Result<String> Forget(@RequestBody UserLoginEmalDto userLoginEmalDto) throws Exception {
       String ss=userService.updatepassword(userLoginEmalDto);
        return Result.success(ss);
    }

    //todo 通过tooken获取用户信息
@ApiOperation(value = "根据用户id获取用户信息")
    @GetMapping("/getmassagebyid")
    public Result<UserLogin> GetmessagebyID(){
         Integer idd= BaseContext.getCurrentId().intValue();
      return Result.success(userService.getmassagebyID(idd));
    }
@ApiOperation(value ="用户修改自己的信息")
    @PutMapping("/updatemessagebyid")
    public Result<String> UpdateMessage(@RequestBody UserLogin11 userLogin11){
        UserLogin userLogin=new UserLogin();
    BeanUtils.copyProperties(userLogin11,userLogin);
    userLogin.setId(BaseContext.getCurrentId().intValue());
      userService.updatemessagebyid(userLogin);
       return Result.success("修改成功");
    }

 //古诗收藏的增删查
 @ApiOperation("用户收藏古诗")
@PostMapping("/collect/addpem")
    public Result<String> addPoem(@RequestBody UserCollectionPoemDto userCollectionPoemDto){
        Integer idd=BaseContext.getCurrentId().intValue();
        userCollectionPoemDto.setUserid(idd);
        if(!userService.findPoem(userCollectionPoemDto)){
      userService.addPoem(userCollectionPoemDto);
            return Result.success("收藏成功");
        }
     else {
         return Result.error("已经收藏过了");
        }
 }
 @ApiOperation("用户取消收藏古诗")
    @DeleteMapping("/collect/deletepem")
    public Result<String> deletePoem(@RequestBody UserCollectionPoemDto userCollectionPoemDto){
     Integer idd=BaseContext.getCurrentId().intValue();
     userCollectionPoemDto.setUserid(idd);
      userService.deletePoem(userCollectionPoemDto);
      return Result.success("取消收藏成功");
 }
 @ApiOperation("通过用户id返回用户收藏古诗的id组")
 @GetMapping("/collect/ids")
public Result<List<Integer>> getCollectIds(){
        Integer idd=BaseContext.getCurrentId().intValue();
    List<Integer> list=userService.getCollectIds(idd);
    return Result.success(list);
}

@ApiOperation("查看用户自己收藏的古诗")
@GetMapping("/collect")
public Result<List<PoemDataVo>> getCollect(){
    Integer idd=BaseContext.getCurrentId().intValue();
   List<PoemDataVo> list1=userService.getCollect(idd);
   return Result.success(list1);
}
//名句收藏的增删查
@ApiOperation("用户收藏名句")
@PostMapping("/collect/addrhesis")
public Result<String> addrhesis(@RequestBody UserCollectionRhesisDto userCollectionRhesisDto){
    userService.addrhesis(userCollectionRhesisDto);
    return Result.success("收藏成功");
}
    @ApiOperation("用户取消收藏名句")
    @DeleteMapping("/collect/deleterhesis")
    public Result<String> deletePoem(@RequestBody UserCollectionRhesisDto userCollectionRhesisDto){
        userService.deletethesis(userCollectionRhesisDto);
        return Result.success("取消收藏成功");
    }
    @ApiOperation("通过用户id返回用户收藏名句的id组")
    @GetMapping("/collect/rhesisids/{id}")
    public Result<List<Integer>> getCollectResis(@PathVariable Integer id){
        List<Integer> list=userService.getCollectResis(id);
        return Result.success(list);
    }
    @ApiOperation("查看用户自己收藏的古诗")
    @GetMapping("/collectRhesis/{id}")
    public Result<List<RhesisDataVo>> getCollectRhesesss(@PathVariable Integer id){
        List<RhesisDataVo> list1=userService.getCollectRhesis(id);
        return Result.success(list1);
    }
//作者收藏的增删查------------------------缺少数据




//用户的学习诗词表
    @ApiOperation(value = "诗词表初实化")
    @PostMapping("/book/statr")
    public Result<String> star(@RequestBody UserBook userBook){
        userBook.setUserid(BaseContext.getCurrentId().intValue());
        Long dagree=BaseContext.getDagree();
        userService.adduserbook1(userBook,dagree);
        return Result.success("初始化成功");
    }

    @ApiOperation(value = "自定义诗词表")
    @PostMapping("/book/add")
    public Result<String> add(@RequestBody UserBookDto userBookDto){
        UserBook userBook=new UserBook();
        BeanUtils.copyProperties(userBookDto,userBook);
        userBook.setUserid(BaseContext.getCurrentId().intValue());
        userService.adduserbook(userBook);
        return Result.success("创建诗词表成功");
    }
   @ApiOperation(value = "向诗词表中，添加古诗，逻辑是点击一首古诗后，弹出自定义诗词表")
    @PostMapping("/book/addpoem")
    public Result<String> addpoem(@RequestBody UserBookPoemDtodto userBookPoemDtodto){
       UserBookPoemDto userBookPoemDto=new UserBookPoemDto();
       BeanUtils.copyProperties(userBookPoemDtodto,userBookPoemDto);
        userService.addPoemword(userBookPoemDto);
        return Result.success("添加古诗成功");
    }
@ApiOperation(value="展示所有诗词表")
    @GetMapping("/book/show")
    public Result<List<UserBook>> show(){
       Integer idd=BaseContext.getCurrentId().intValue();
       log.info("当前用户id：{}",idd);
       List<UserBook> list=userService.show(idd);
       return Result.success(list);
    }
  @ApiOperation(value = "展示这个诗词表里面的全部诗")
    @GetMapping("/book/showpoem/{bookid}")
    public Result<List<PoemDataVo>> showpoem(@PathVariable Integer bookid){
       List<PoemDataVo> list=userService.showpoem(bookid);
       return Result.success(list);
    }

 @ApiOperation(value = "开始计划初始化表格")
    @PostMapping("/book/start")
    public Result<String> start(@RequestParam Integer bookId,@RequestParam (defaultValue = "1")Integer much){
       Integer id=BaseContext.getCurrentId().intValue();
       userService.start1(bookId,id,much);
        return Result.success("初始化成功");
    }
@ApiOperation(value = "展示计划表格")
    @GetMapping("/book/showplan/{bookid}")
    public Result<List<PlanDataVo>> showplan(@PathVariable Integer bookid){
       List<PlanDataVo> list=userService.showplan(bookid);
       return Result.success(list);
    }
 @ApiOperation(value = "查看我的评论")
    @GetMapping("user/comment")
    private Result<List<PoemLunTanCommentVo> > selectcomment(){
       Integer id=BaseContext.getCurrentId().intValue();
       List<PoemLunTanCommentVo> list=userService.selectcomment(id);
       return Result.success(list);
    }
@ApiOperation(value = "删除我的评论")
    @DeleteMapping("/user/comment/delete/{commentid}")
    private Result<String> deleteComment(@PathVariable Integer commentid){
       userService.deleteComment(commentid);
       return Result.success("删除成功");
    }

}
