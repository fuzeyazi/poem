package com.fuze.potryservice.mapper;

import com.fuze.dto.*;
import com.fuze.vo.BlogUserVo;
import com.fuze.vo.FabaCommnetVo;
import com.fuze.vo.PoemBlogVo;
import com.fuze.vo.UserBlogListVo;
import com.github.pagehelper.Page;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface PoemLunTanMapper {


    void fabu1(Integer blogid,PoemBlogDto poemBlogDto, Integer idd);
@Select("select * from poem.poem_blog where id=#{blogid}")
PoemBlogDtoSuper selectxiangxi(Integer blogid);
@Update("update poem.poem_blog set liked=liked+1 where id=#{blogid}")
    void updatedianzan(Integer blogid);
    @Update("update poem.poem_blog set liked=liked-1 where id=#{blogid}")
    void updatequxiaodianzan(Integer blogid);
@Insert("insert into poem.tb_follow(user_Id,follow_user_id) values(#{userid},#{followUserid})")
    void insertguanzhu(Integer followUserid, Integer userid);
@Delete("delete from poem.tb_follow where user_Id=#{userid} and follow_user_id=#{followUserid}")
    void deleteguanzhu(Integer followUserid, Integer userid);


@Select("SELECT * FROM poem.tb_follow WHERE follow_user_id=#{followUserid} and user_Id=#{userid}")
    Integer isfrend1(Integer followUserid, Integer userid);
@Select("select b.*,u.touxiang,u.username from poem.poem_blog b, poem.user u  where type like CONCAT('%',#{type},'%') and u.id=b.user_id ")
    Page<PoemBlogVo> GetPoemPage(String type);
@Select("select * from poem.user where username=#{username}")
    BlogUserVo getByUsername();
@Select("select * from poem.user where id=#{followid}")
    BlogUserVo getByUsername1(Integer followid);
@Select("select * from poem.poem_blog where user_id=#{followid}")
    Page<UserBlogListVo> selecttiezi(Integer followid);
@Select("select user_id from poem.tb_follow where follow_user_id=#{id}")
    List<Integer> getuseridbylistid(Integer id);
@Select("select max(id)from poem.poem_blog where user_id=#{id}")
    Integer fabu(Integer id);

    void fabu12(PoemBlogDtoPlus poemBlogDtoPlus);
@Select("select * from poem.poem_blog where id in (#{ids}) order by field(id,#{ids})  ")
    List<PoemBlogVo> selecttieziy(List<Long> ids);
@Insert("INSERT INTO poem.forum_comment(blog_id, user_id, context,parent_id,tagerr_name) value (#{fourmCommentDto.blogId},#{id},#{fourmCommentDto.context},#{fourmCommentDto.parentId},#{fourmCommentDto.tagerrName})")
    void fabucomment(FourmCommentDto fourmCommentDto, Integer id);
@Update("update poem.poem_blog set conmments=conmments+1 where id=#{blogId}")
    void addblogcomment(Integer blogId);

    List<FabaCommnetVo> selectConmmets(Integer blogid);
@Select("SELECT parent_id,conment FROM  poem.forum_comment WHERE blog_id=#{blogid}")
    List<FourmCommentDto> selectConmmet(Integer blogid);
@Select("SELECT * FROM  poem.forum_comment WHERE blog_id=#{blogid}")
    List<FourCommentDtoPlus> selectConmme1t(Integer blogid);
@Select("SELECT b.*,u.touxiang,u.name from poem.forum_comment b ,poem.user u where blog_id=#{blogid} and u.id=b.user_id")
    List<FabaCommnetVo> selectConmme1t1(Integer blogid);
@Update("update poem.forum_comment set conment=conment+1 where id=#{parentId}")
    void addcomment(Integer parentId);
@Select("select user_id from poem.poem_blog where id=#{blogid}")
    Integer getUserid(Integer blogid);
@Update("update poem.user set fans=fans+1 where id=#{followUserid}")
    void addfans(Integer followUserid);
@Update("update poem.user set fans=fans-1 where id=#{followUserid}")
    void deletefans(Integer followUserid);
@Select("SELECT * FROM poem.tb_follow WHERE follow_user_id=#{followUserid} and user_Id=#{userid}")
    List<Integer> isfrend11(Integer followUserid, Integer userid);
@Update("update poem.forum_comment set  liked=liked+1 where id=#{commentid}")
    void updatedianzan1(Integer commentid);
@Update("update poem.forum_comment set  liked=liked-1 where id=#{commentid}")
    void updatequxiaodianzan1(Integer commentid);
}
