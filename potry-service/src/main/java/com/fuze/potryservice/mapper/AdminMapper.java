package com.fuze.potryservice.mapper;

import com.fuze.dto.PotryDTO;
import com.fuze.dto.RhesisDto;
import com.fuze.entity.*;
import com.fuze.vo.PoemBlogVo;
import com.github.pagehelper.Page;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface AdminMapper {
@Select("select * from poem.admin where username=#{username}")
Admin getByUsername(String username);
    @Insert("INSERT INTO poem.potry(title, dynasty, writer, type, content) " +
            "VALUES (#{title}, #{dynasty}, #{writer}, #{type}, #{content})")
    void insert(PotryDTO potryDTO);
@Delete("delete from poem.potry where id in (#{ids})")
    void delete(Long id);
@Insert("INSERT INTO poem.admin(username, password, email, phone,status,created_at,updated_at) " + "VALUES(#{username}, #{password}, #{email}, #{phone},#{status},#{createdAt},#{updatedAt})")
    void register(Admin admin);
@Select("select * from poem.admin where email=#{email}")
    Boolean getByemail(String email);

    void update(PotryDTO potryDTO);
@Select("select * from poem.potry where title=#{title}")
Poem getbyTitle(String title);

    List<PotryDTO> GetContent(PotryDTO potryDTO);
@Delete("delete from poem.potry where title=#{title}")
    void deleteByTitle(String title);
@Insert("INSERT INTO poem.suggestion(id,content,created_at) " + "VALUES(#{id},#{content},#{createdAt})")
    void save(Suggestion suggestion);
    @Select("SELECT content FROM poem.comment WHERE parent_id=#{id} AND status=#{status}")
    List<String> GetListBy(Integer id, int status);
@Select("SELECT * FROM poem.poem_blog")
    List<PoemBlog> GetPage();
@Select("SELECT * FROM poem.user")
    Page<UserJo> GetUser();
@Select("SELECT * FROM poem.potry")
    Page<Poem> GetPoem();
@Select("SELECT * FROM poem.poem_blog")
    Page<PoemBlog> GetBlog();
@Delete("delete from poem.poem_blog where id=#{id}")
    void deleteBlogById(Integer id);
@Select("SELECT * FROM poem.rhesis")
    Page<Rhesis> GetRhesis();
@Delete("delete from poem.rhesis where id=#{id}")
    void deleteRhesisById(Integer id);
@Insert("INSERT INTO poem.rhesis(name,fromm) " + "VALUES(#{name},#{fromm})")
    void addRhesis(RhesisDto rhesisDto);

    void updateRhesis(RhesisDto rhesisDto);
    List<RhesisDto> GetRhesisByPoemName(String name);
}
