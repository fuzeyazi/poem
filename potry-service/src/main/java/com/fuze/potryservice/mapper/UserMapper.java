package com.fuze.potryservice.mapper;

import com.fuze.dto.*;
import com.fuze.entity.RhesisDataVo;
import com.fuze.entity.UserBook;
import com.fuze.entity.UserJo;
import com.fuze.vo.PlanDataVo;
import com.fuze.vo.PoemDataVo;
import com.fuze.vo.PoemLunTanCommentVo;
import org.apache.catalina.User;
import org.apache.ibatis.annotations.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Mapper
public interface UserMapper {

@Select("select * from poem.user where username=#{username}")
UserJo loginbyusername1(String username);
@Select("select * from poem.user where username=#{username}")
    UserJo getbynamme(String username);
@Insert("insert into poem.user(password,username,name,phone,sex,openid,email)value(#{password},#{username},#{name},#{phone},#{sex},#{openid},#{email})")
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
@Select("select * from poem.user where email=#{email}")
    UserJo findByEmail(String email);
@Select("select id from poem.user where email=#{email}")
    Integer findidbyemail(String email);
@Select("select * from poem.usercollectionpoem where userid=#{userid} and poemid=#{poemid}")
    Integer findPoem(UserCollectionPoemDto userCollectionPoemDto);
@Select("select password from poem.user where email=#{email}")
    String getpassword(String email);
@Update("update poem.user set password=#{password} where email=#{email}")
    void updatemessagebyid1(UserLoginEmalDto userLoginEmalDto);


@Select("select id from poem.potry  where type like CONCAT('%',#{dagree1},'%')  ")
    List<Integer> getpoemidbydagree(String dagree1);
@Insert("INSERT INTO poem.userbook(user_id,book_name,description) VALUES (#{userid},#{bookname},#{description})")
    void adduserbook11(UserBook userBook, List<Integer> keys);
@Insert("INSERT INTO poem.userbook(user_id,book_name,description) VALUES (#{userid},#{bookname},#{description})")
    void adduserbook(UserBook userBook);
@Insert("INSERT INTO poem.userbookpoem(book_id,poem_id,lastReviewDate) VALUES (#{bookid},#{poemid},#{lastReviewDate})")
    void addPoemword(UserBookPoemDto userBookPoemDto);
@Update("UPDATE poem.userbook set sum=sum+1 where book_id=#{poemid}")
    void updatePowmWord(Integer poemid);
@Select("select * from poem.userbook where user_id=#{idd}")
    List<UserBook> show(Integer idd);
@Select("select poem_id from poem.userbookpoem where book_id=#{bookid}")
    List<Integer> getpoemidbybookid(Integer bookid);

    List<PoemDataVo> showpoem(List<Integer> keys);
@Select("select u.*from poem.userbookpoem u,poem.userbook b where user_id=#{userid}")
    List<UserBookPoemDto> findByUserid(Integer userId);
@Select("select count(*) from poem.userbookpoem where book_id=#{bookid}")
    int getsum(Integer bookid, Integer id);
@Update("UPDATE poem.userbookpoem SET reviewCount=0,lastReviewDate=#{zz} where book_id=#{bookId}")
    void updatatep(Integer bookId, Integer id, LocalDateTime zz);
    @Select("select * from poem.userbookpoem where poem_id=#{poemid} and book_id=#{bookid}")
    boolean findPoembybookid1(UserBookPoemDto userBookPoemDto);

    void batchUpdatatep(Integer bookId, Integer id, List<LocalDateTime> dates,List<Integer> poemid) ;

    void batchUpdatatep1(Map<String, Object> params);
    @Update("UPDATE poem.userbookpoem SET reviewCount=0,lastReviewDate=#{zz} where book_id=#{bookId} and poem_id=#{integer1}")
    void updatatep1(Integer bookId, Integer integer, LocalDateTime zz, Integer integer1);
@Select("select * from poem.userbookpoem where book_id=#{bookid}")
    List<PlanDataVo> showplan(Integer bookid);


    @Select("SELECT * FROM poem.user WHERE id IN (#{userIds})")
    List<UserJo> getuserbylistid(@Param("userIds") List<Integer> userIds);
@Select("select name_tager from poem.user where id=#{userId}")
    String getuserTagerbyid(Integer userId);
@Select("select fans from poem.user where id=#{userid}")
    Integer getfans(Integer userid);
@Select("select id,blog_id,context from poem.forum_comment where user_id=#{id}")
    List<PoemLunTanCommentVo> selectcomment(Integer id);
@Delete("delete from poem.forum_comment where id=#{commentid}")
    void deleteComment(Integer commentid);
}
