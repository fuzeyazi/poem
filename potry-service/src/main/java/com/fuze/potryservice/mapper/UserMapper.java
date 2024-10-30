package com.fuze.potryservice.mapper;

import com.fuze.dto.UserCollectionPoemDto;
import com.fuze.dto.UserCollectionRhesisDto;
import com.fuze.dto.UserLogin;
import com.fuze.entity.RhesisDataVo;
import com.fuze.entity.UserJo;
import com.fuze.vo.PoemDataVo;
import org.apache.catalina.User;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface UserMapper {

@Select("select * from poem.user where username=#{username}")
UserJo loginbyusername1(String username);
@Select("select * from poem.user where username=#{username}")
    UserJo getbynamme(String username);
@Insert("insert into poem.user(password,username,name,phone,sex,openid)value(#{password},#{username},#{name},#{phone},#{sex},#{openid})")
    void adduser(UserJo newuser);
@Select("select openid from poem.user where id=#{id}")
    String getopid(int id);
@Select("select roleid from poem.airole where name=#{name}")
    String getroleid(String name);
@Insert("INSERT INTO poem.airole(name, roleid) VALUE (#{name},#{roleid})")
    void setAgentId(String agentName, String data);
@Select("select chatid from poem.airole where name=#{name}")
    String ischaid(String name);
@Update("UPDATE poem.airole SET chatid = NULL WHERE name = #{name}")
    void deleteCharacter(String name);
@Insert("INSERT into poem.airole(chatid) value (#{chatid})")
    void insertchatId(String chatId);
@Update("update poem.airole set chatid=chatid WHERE roleid=#{roleid}")
    void updachatId(String chatId,String roleid );
@Select("SELECT * FROM poem.user WHERE id=#{id}")
UserLogin getmassagebyID(Integer id);

    void updatemessagebyid(UserLogin userLogin);
    //古诗
@Insert("INSERT INTO poem.usercollectionpoem(userid, poemid) VALUE (#{userid},#{poemid})")
    void addPoem(UserCollectionPoemDto userCollectionPoemDto);
@Delete("DELETE FROM poem.usercollectionpoem WHERE userid=#{userid} and poemid=#{poemid}")
    void deletepoem(UserCollectionPoemDto userCollectionPoemDto);
@Select("SELECT p.title,p.content,p.writer,p.type from poem.potry p,poem.usercollectionpoem u where u.userid=#{id} and u.poemid=p.id")
    List<PoemDataVo> getcollecterct(Integer id);
@Select("SELECT poemid from poem.usercollectionpoem where userid=#{id}")
    List<Integer> getCollectIds(Integer id);
//名句
    @Insert("INSERT INTO poem.userlikerhesis(userid, rhesisid) VALUE (#{userid},#{rhesisid})")
    void addrhesis(UserCollectionRhesisDto userCollectionRhesisDto);
    @Delete("DELETE from poem.userlikerhesis where userid=#{userid} and rhesisid=#{rhesisid}")
    void deletehesis(UserCollectionRhesisDto userCollectionRhesisDto);
   @Select("select rhesisid from poem.userlikerhesis where userid=#{id}")
    List<Integer> getCollectResis(Integer id);
@Select("select r.name,r.fromm from poem.userlikerhesis u,poem.rhesis r where u.userid=#{id} and u.rhesisid=r.id")
    List<RhesisDataVo> getCollectRhesis(Integer id);
@Select("SELECT touxiang from poem.user where id=#{id}")
    String gettouxiangbyid(Integer userid);
@Select("select username from poem.user where id=#{id}")
    String getusernamebyid(Integer userid);
}
