package com.fuze.potryservice.mapper;

import com.fuze.vo.GameRankVo;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface QuestionGameMapper {
    @Insert("INSERT INTO poem.questionsgame(answer) VALUE (#{answer})")
    void addQuestion(String s);
@Select("select * from poem.questionsgame")
    String getquestion();
@Delete("delete from poem.questionsgame")
    void deleteQuestion();
@Insert("INSERT INTO poem.gamerank(grand,userid,usename) value (#{grand},#{userid},#{username})")
    void addsum(int grand, Integer userid,String userName);
@Select("select username from poem.user where id=#{id}")
    String getusename(Integer userId);
@Select("select DISTINCT * from poem.gamerank order by grand desc limit 20")
    List<GameRankVo> getRank();
@Select("select * from poem.gamerank")
    List<GameRankVo> getalluser();
@Delete("DELETE FROM poem.gamerank WHERE userid=#{userid}")
    void delete(Integer id);
@Select("select * from poem.gamerank where userid=#{userid}")
    List<GameRankVo> getuserRanl(Integer userid);
}
