package com.fuze.potryservice.mapper;

import com.fuze.dto.*;
import com.fuze.entity.RhesisDataVo;
import com.fuze.entity.UserBook;
import com.fuze.entity.UserJo;
import com.fuze.vo.PlanDataVo;
import com.fuze.vo.PoemDataVo;
import com.fuze.vo.PoemLunTanCommentVo;
import com.fuze.vo.TodayReviewVo;
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
@Insert("insert into poem.user(password,username,name,phone,sex,openid,email,touxiang)values(#{password},#{username},#{name},#{phone},#{sex},#{openid},#{email},#{touxiang})")
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
@Insert("INSERT into poem.airole(chatid) values(#{chatid})")
    void insertchatId(String chatId);
@Update("update poem.airole set chatid=chatid WHERE roleid=#{roleid}")
    void updachatId(String chatId,String roleid );
@Select("SELECT * FROM poem.user WHERE id=#{id}")
UserLogin getmassagebyID(Integer id);

    void updatemessagebyid2(UserLogin userLogin);

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
@Options(useGeneratedKeys = true, keyProperty = "bookid")
    void adduserbook(UserBook userBook);
/** 建书后按学历批量配诗(修复原查询结果被丢弃的断链);next=加入日+1天,即艾宾浩斯首次复习 */
@Insert("<script>INSERT INTO poem.userbookpoem(book_id,poem_id,reviewCount,lastReviewDate,nextReviewDate) VALUES " +
        "<foreach collection='keys' item='pid' separator=','>" +
        "(#{bookid},#{pid},0,NOW(),NOW())" +
        "</foreach></script>")
    void addBookPoemsBatch(@Param("bookid") Integer bookid, @Param("keys") List<Integer> keys);
@Insert("INSERT INTO poem.userbookpoem(book_id,poem_id,reviewCount,lastReviewDate,nextReviewDate) VALUES (#{bookid},#{poemid},0,NOW(),NOW())")
    void addPoemword(UserBookPoemDto userBookPoemDto);
@Update("UPDATE poem.userbook set sum=sum+1 where book_id=#{poemid}")
    void updatePowmWord(Integer poemid);
/** 建书配诗后校正总数(批量加入n首) */
@Update("UPDATE poem.userbook set sum=sum+#{n} where book_id=#{bookid}")
    void updateBookSum(@Param("bookid") Integer bookid, @Param("n") int n);
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
    /** 收入书架查重: 原boolean基本类型接收null(未收藏时)直接BindingException,收入书架自上线即100%失败 */
    @Select("select count(*) from poem.userbookpoem where poem_id=#{poemid} and book_id=#{bookid}")
    Integer findPoembybookid1(UserBookPoemDto userBookPoemDto);

    void batchUpdatatep(Integer bookId, Integer id, List<LocalDateTime> dates,List<Integer> poemid) ;

    @Update("UPDATE poem.userbookpoem SET reviewCount=0,lastReviewDate=#{zz} where book_id=#{bookId} and poem_id=#{integer1}")
    void updatatep1(Integer bookId, Integer integer, LocalDateTime zz, Integer integer1);
/** 排期批量化:按id序每much首一组,学习日=今天起逐日+1;学习当天即进入今日任务(next=学习日),首轮复习后由SRS推进到+3天 */
@Update("UPDATE poem.userbookpoem p JOIN " +
        "(SELECT id, DATE_ADD(#{startDate}, INTERVAL (FLOOR((ROW_NUMBER() OVER (ORDER BY id) - 1) / #{much})) DAY) AS learnDate " +
        " FROM poem.userbookpoem WHERE book_id=#{bookId}) t ON p.id=t.id " +
        "SET p.reviewCount=0, p.lastReviewDate=t.learnDate, p.nextReviewDate=t.learnDate")
    int scheduleBatch(@Param("bookId") Integer bookId, @Param("much") int much, @Param("startDate") LocalDateTime startDate);
/** 今日应复习:nextReviewDate已到期(走idx_book_next),按到期先后排序 */
@Select("SELECT p.poem_id AS poemid, b.title, b.writer, b.content, b.dynasty, " +
        "p.reviewCount, p.nextReviewDate " +
        "FROM poem.userbookpoem p JOIN poem.potry b ON b.id=p.poem_id " +
        "WHERE p.book_id=#{bookid} AND p.nextReviewDate IS NOT NULL AND p.nextReviewDate<=NOW() " +
        "ORDER BY p.nextReviewDate")
    List<TodayReviewVo> getTodayReviews(Integer bookid);
    /** 复习曲线原始行(按日聚合在服务层做) */
    @Select("select poem_id, reviewCount, lastReviewDate, nextReviewDate from poem.userbookpoem where book_id=#{bookid}")
    List<UserBookPoemDto> getBookPoemRows(Integer bookid);


//    @Select("SELECT * FROM poem.user WHERE id IN (#{userIds})")
    List<UserJo> getuserbylistid(@Param("userIds") List<Integer> userIds);
@Select("select name_tager from poem.user where id=#{userId}")
    String getuserTagerbyid(Integer userId);
@Select("select fans from poem.user where id=#{userid}")
    Integer getfans(Integer userid);
@Select("select id,blog_id,context from poem.forum_comment where user_id=#{id}")
    List<PoemLunTanCommentVo> selectcomment(Integer id);
@Delete("delete from poem.forum_comment where id=#{commentid}")
    void deleteComment(Integer commentid);

    void update(UserJo userJo);

    @Update({
            "<script>",
            "UPDATE poem.user",
            "<set>",
            "  <if test='username != null'>username = #{username},</if>",
            "  <if test='password != null'>password = #{password, jdbcType=VARCHAR},</if>",
            "  <if test='name != null'>name = #{name},</if>",
            "  <if test='touxiang != null'>touxiang = #{touxiang},</if>",
            "  <if test='phone != null'>phone = #{phone},</if>",
            "  <if test='email != null'>email = #{email},</if>",
            "  <if test='sex != null'>sex = #{sex},</if>",
            "  <if test='age != null'>age = #{age},</if>",
            "  <if test='degree != null'>degree = #{degree}</if>",
            "</set>",
            "WHERE id = #{id}",
            "</script>"
    })
    int updatemessagebyid213(UserLogin userLogin);


    /** 复习提醒: 全部到期用户及各自到期数(走idx_book_next范围扫描) */
    @Select("SELECT ub.user_id AS userId, COUNT(*) AS cnt FROM poem.userbook ub " +
            "JOIN poem.userbookpoem ubp ON ubp.book_id = ub.book_id " +
            "WHERE ubp.nextReviewDate IS NOT NULL AND ubp.nextReviewDate <= NOW() " +
            "GROUP BY ub.user_id")
    java.util.List<java.util.Map<String, Object>> GetDueReviewUsers();

    /** 当前用户今日到期待复习数(红点接口) */
    @Select("SELECT COUNT(*) FROM poem.userbookpoem ubp WHERE ubp.book_id IN " +
            "(SELECT book_id FROM poem.userbook WHERE user_id = #{uid}) " +
            "AND ubp.nextReviewDate IS NOT NULL AND ubp.nextReviewDate <= NOW()")
    Integer GetDueReviewCount(@Param("uid") Long uid);
}