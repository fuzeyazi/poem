package com.fuze.potryservice.controller.user;

import com.fuze.constant.MessageConstant;
import com.fuze.context.BaseContext;
import com.fuze.dto.*;
import com.fuze.entity.RhesisDataVo;
import com.fuze.entity.UserJo;
import com.fuze.exception.AccountNotFoundException;
import com.fuze.potryservice.service.UserService;
import com.fuze.properties.JwtProperties;
import com.fuze.constant.JwtClaimsConstant;
import com.fuze.result.Result;
import com.fuze.utils.JwtUtil;
import com.fuze.vo.PoemDataVo;
import com.fuze.vo.UserLoginVo;
import com.fuze.vo.UserVo;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;

import org.apache.catalina.User;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.util.DigestUtils;
import org.springframework.web.bind.annotation.*;

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
            String token = JwtUtil.createJWT(jwtProperties.getUserSecretKey(), jwtProperties.getUserTtl(), claims);
            UserVo userVo = UserVo.builder()
                    .id(user1.getId())
                    .username(user1.getUsername())
                    .name(user1.getName())
                    .openid(user1.getOpenid())
                    .token(token)
                    .build();
            return Result.success(userVo);
        } catch (Exception e) {
            log.error("Error during user login", e);
            return Result.error("Internal server error");
        }
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
    //todo 通过tooken获取用户信息
@ApiOperation(value = "根据用户id获取用户信息")
    @GetMapping("/getmassagebyid/{id}")
    public Result<UserLogin> GetmessagebyID(
            @PathVariable("id") Integer id){
         Integer idd=  BaseContext.getCurrentId().intValue();

      return Result.success(userService.getmassagebyID(idd));
    }
@ApiOperation(value ="用户修改自己的信息")
    @PutMapping("/updatemessagebyid")
    public Result<String> UpdateMessage(@RequestBody UserLogin userLogin){
      userService.updatemessagebyid(userLogin);
       return Result.success("修改成功");
    }

 //古诗收藏的增删查
 @ApiOperation("用户收藏古诗")
@PostMapping("/collect/addpem")
    public Result<String> addPoem(@RequestBody UserCollectionPoemDto userCollectionPoemDto){
      userService.addPoem(userCollectionPoemDto);
      return Result.success("收藏成功");
 }
 @ApiOperation("用户取消收藏古诗")
    @DeleteMapping("/collect/deletepem")
    public Result<String> deletePoem(@RequestBody UserCollectionPoemDto userCollectionPoemDto){
      userService.deletePoem(userCollectionPoemDto);
      return Result.success("取消收藏成功");
 }

 @ApiOperation("通过用户id返回用户收藏古诗的id组")
 @GetMapping("/collect/ids/{id}")
public Result<List<Integer>> getCollectIds(@PathVariable Integer id){
    List<Integer> list=userService.getCollectIds(id);
    return Result.success(list);
}

@ApiOperation("查看用户自己收藏的古诗")
@GetMapping("/collect/{id}")
public Result<List<PoemDataVo>> getCollect(@PathVariable Integer id){
   List<PoemDataVo> list1=userService.getCollect(id);
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







}
