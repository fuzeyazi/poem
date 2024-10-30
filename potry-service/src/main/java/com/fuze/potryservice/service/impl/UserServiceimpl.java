package com.fuze.potryservice.service.impl;

import com.fuze.constant.MessageConstant;
import com.fuze.dto.UserCollectionPoemDto;
import com.fuze.dto.UserCollectionRhesisDto;
import com.fuze.dto.UserLogin;
import com.fuze.dto.UserLoginDto;
import com.fuze.entity.RhesisDataVo;
import com.fuze.entity.UserJo;
import com.fuze.exception.AccountNotFoundException;
import com.fuze.potryservice.mapper.UserMapper;
import com.fuze.potryservice.service.UserService;

import com.fuze.utils.PlayerUtil;
import com.fuze.vo.PoemDataVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class UserServiceimpl implements UserService {
@Autowired
private  UserMapper userMapper;
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
        userMapper.updatemessagebyid( userLogin);
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
}
