package com.fuze.potryservice.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fuze.entity.Comment;
import com.fuze.vo.CommentVo;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.util.List;
import java.util.Optional;

@Mapper
public interface CommentMapper extends BaseMapper<CommentVo> {
    @Insert("INSERT INTO poem.comment(content,user_id,touxiang,username) value (#{content},#{userid},#{touxiang},#{username})")
    void addcomment(Comment comment);
    @Update("UPDATE poem.comment SET thumbs_up = thumbs_up + 1 WHERE id = #{id}")
    void addthumb(Integer id);
@Update("UPDATE poem.comment SET thumbs_down = thumbs_down + 1 WHERE id = #{id}")
    void deletethumb(Integer id);
@Update("UPDATE poem.comment SET replycount = replycount + 1 WHERE id = #{parentid}")
    void addreplycount(Integer parentid);
    @Insert("INSERT INTO poem.comment(content,user_id,touxiang,username,parent_id) value (#{content},#{userid},#{touxiang},#{username},#{parentid})")
    void addcommentparentid(Comment comment);
    List<CommentVo> getCommentList();
    @Select("select * from poem.comment where id=#{id}")
    Comment findbyid(Integer id);

    @Select("select * from poem.comment where parent_id=#{id}")
    List<Comment> findByParentId(Integer id);
}
