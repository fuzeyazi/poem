package com.fuze.potryservice.mapper;

import com.fuze.dto.FeedBackDto;
import com.fuze.dto.ReplyDto;
import com.fuze.entity.FeedBack;
import com.fuze.vo.FeedBackVo;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface FeedBackMapper {

    // 注意：如果数据库表字段名为 'messsage'，请确保这是正确的意图或已修正
    @Insert("INSERT INTO poem.feedback(userid, messsage) VALUES (#{userid}, #{message})")
    void addfeedback(FeedBackDto feedBackDto);
@Select("SELECT * FROM poem.feedback")
    List<FeedBack> getAllFeedBack();
@Select("SELECT * FROM poem.feedback WHERE id = #{id}")
    FeedBack getFeedBack(Integer id);
@Delete("DELETE FROM poem.feedback WHERE id = #{id}")
    void deletefeedback(Integer id);
@Insert("insert into poem.reply(userid, feedbackid, message) value (#{userid},#{feedbackid},#{message})")
    void addreply(ReplyDto replyDto);
@Select("SELECT * FROM poem.feedback")
    List<FeedBackVo> Getpage();
@Select("SELECT message from  poem.reply where userid=#{id}")
    String getReply(Integer id);
}

