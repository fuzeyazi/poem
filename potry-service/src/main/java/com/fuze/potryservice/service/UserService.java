package com.fuze.potryservice.service;

import com.fuze.dto.*;
import com.fuze.entity.RhesisDataVo;
import com.fuze.entity.UserBook;
import com.fuze.entity.UserJo;
import com.fuze.vo.PlanDataVo;
import com.fuze.vo.PoemDataVo;
import com.fuze.vo.PoemLunTanCommentVo;
import jakarta.mail.MessagingException;
import jakarta.servlet.http.HttpSession;

import java.io.UnsupportedEncodingException;
import java.util.List;
import java.util.Map;

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

    String sendcode(String phone, HttpSession session,Integer status) throws UnsupportedEncodingException, MessagingException;

    String loginEmal(UserLoginEmalDto userLoginEmalDto);


    boolean findPoem(UserCollectionPoemDto userCollectionPoemDto);


    String updatepassword(UserLoginEmalDto userLoginEmalDto);
    void adduserbook1(UserBook userBook, Long dagree);

    void adduserbook(UserBook userBook);
    void addPoemword(UserBookPoemDto userBookPoemDto);

    List<UserBook> show(Integer idd);

    List<PoemDataVo> showpoem(Integer bookid);

    Map<String, Integer> getForgetCurve(Integer userId);

    void createReviewPlan1(Integer userId, Integer bookId);

    void start(UserBook userBook, Integer id);

    void start1(Integer bookId, Integer id, Integer much);

    List<PlanDataVo> showplan(Integer bookid);

    List<PoemLunTanCommentVo> selectcomment(Integer id);

    void deleteComment(Integer commentid);

    UserJo login11(UserLoginEmalDtoPlus userLoginEmalDtoPlus);
}
