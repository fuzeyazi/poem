package com.fuze.potryservice.service;

import com.fuze.dto.UserCollectionPoemDto;
import com.fuze.dto.UserCollectionRhesisDto;
import com.fuze.dto.UserLogin;
import com.fuze.dto.UserLoginDto;
import com.fuze.entity.RhesisDataVo;
import com.fuze.entity.UserJo;
import com.fuze.vo.PoemDataVo;

import java.util.List;

public interface UserService {


    UserJo login1(UserLoginDto userLoginDto);


    UserJo getByUsername(String username);

    void adduser(UserJo newuser) throws Exception;

    String getopid(int id);

    String getroleid(String name);

    String ischaid(String name);

    void deleteCharacter(String name);

    void insertchatId(String chatId);

    void updachatId(String chatId, String roleid);

    UserLogin getmassagebyID(Integer id);

    void updatemessagebyid(UserLogin userLogin);

    void addPoem(UserCollectionPoemDto userCollectionPoemDto);

    void deletePoem(UserCollectionPoemDto userCollectionPoemDto);

    List<PoemDataVo> getCollect(Integer id);

    List<Integer> getCollectIds(Integer id);

    void addrhesis(UserCollectionRhesisDto userCollectionRhesisDto);

    void deletethesis(UserCollectionRhesisDto userCollectionRhesisDto);

    List<Integer> getCollectResis(Integer id);

    List<RhesisDataVo> getCollectRhesis(Integer id);

    String gettouxiangbyid(Integer userid);

    String getusernamebyid(Integer userid);
}
