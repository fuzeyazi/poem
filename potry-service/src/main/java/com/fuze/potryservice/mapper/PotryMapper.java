package com.fuze.potryservice.mapper;

import com.fuze.entity.Poem;
import com.fuze.entity.Writer;
import com.fuze.entity.WriterEndVo;
import com.fuze.result.PageResult;
import com.fuze.vo.*;
import com.github.pagehelper.Page;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;
import org.springframework.cache.annotation.CacheEvict;

import java.util.List;
import java.util.Map;
import java.util.Set;

@Mapper
public interface PotryMapper {
    @Select("select count(*) from poem.potry")
    Integer getcount();

    @Select("select title from poem.potry")
    List<String> GetAllPoemName();

    @Select("select *  from poem.potry where id=#{id}")
    Poem GetContentById(Integer id);

    @Select("select distinct dynasty from poem.potry")
    List<String> Getdynasty();

    List<DynatryPoemResultVO> GetDynastyPoemResulVo();

    @Select("select id,title,writer,content,type from poem.potry where dynasty LIKE CONCAT('%', #{dynasty}, '%')")
    List<PoemDataVo> GetPoemDataVoByDynasty(String dynasty);
    @Select("select id,title,writer,content,type,dynasty from poem.potry order by rand() limit 10")
    List<PoemDataVo> GetPoemDateRondom();
    @Select("select id,title,dynasty,content,type from poem.potry where writer=#{writer}")
    List<PoemDataVo> GetPoemData(String name);
    @Select("select type from poem.potry")
    List<String> GetType();
    @Select("select title,content,writer,type,dynasty from poem.potry where type like concat('%',#{type},'%')")
    List<PoemDataVo> GetPoemDataByType(String type);
    @Select("select * from  poem.potry where title like CONCAT('%',#{title},'%')")
    List<Poem>  GetContentByTitle(String title);
    @Select("SELECT * FROM poem.potry WHERE id IN(SELECT id FROM (SELECT id FROM poem.potry ORDER BY RAND() LIMIT 10)t)limit 1")
    PoemDataVo GetVeryGoodPoem();
//不使用模糊查询只有输入正确的名字才行
    @Select("SELECT DISTINCT w.id,w.simpleIntro,w.headImageUrl,w.name,w.detailIntro,p.dynasty FROM poem.writer w,poem.potry p WHERE w.id=#{id} and w.name=writer ")
    WriterEndVo GetPoemWriter(int id);

    @Select("SELECT id, title, writer, content, type FROM poem.potry")
    Page<PoemDataVo> GetPoemvoByPage1();
    @Select("select id,writer,title,content,dynasty from poem.potry where dynasty=#{dynasty}")
    Page<PoemVo> GetPoemBydynasty(String dynasty);
    @Select("select  id, title,content,writer,type,dynasty from poem.potry where type like concat('%',#{type},'%')")
    Page<PoemDataVo> GetPoemByType(String type);
@Select("SELECT DISTINCT w.id, w.name, w.headImageUrl, w.simpleIntro, p.dynasty\n" +
        "        FROM poem.writer w\n" +
        "         JOIN poem.potry p ON w.name = p.writer where p.dynasty=#{dyansty}")
    Page<Writer> GetwriterBydynasty(String dynasty);
    @Select("SELECT DISTINCT w.id, w.name, w.headImageUrl, w.simpleIntro, p.dynasty\n" +
            "        FROM poem.writer w\n" +
            "         JOIN poem.potry p ON w.name = p.writer where id IN(SELECT id FROM (SELECT id FROM poem.potry ORDER BY RAND() LIMIT 10)t)limit 1 ")
    PageResult GetwriterBydynasty1();
    @Select("SELECT DISTINCT w.id, w.name, w.headImageUrl, w.simpleIntro, p.dynasty\n" +
            "        FROM poem.writer w\n" +
            "         JOIN poem.potry p ON w.name = p.writer order by rand() limit 10 ")
    List<Writer> GetRondWriter();
    @Select("select  id, title,content,writer,type,dynasty from poem.potry where writer like concat('%',#{writer},'%')")
    Page<PoemDataVo> GetwriterBywriter(String writer);
  @Select("select id,name,fromm from poem.rhesis where fromm like concat(#{writer},'%')")
    Page<RhesisDataVo> GetwriterBywriter1(String writer);
    @Select("select * from  poem.potry where id=#{id}")
    List<Poem> GetContentByTitle1(Integer id);
    @Select("SELECT DISTINCT w.id,w.simpleIntro,w.headImageUrl,w.name,w.detailIntro,p.dynasty FROM poem.writer w,poem.potry p WHERE w.id=#{id} and w.name=writer ")
    List<WriterEndVo> GetPoemWriter1(int id);
@Select("select * from poem.potry where title like concat('%',#{title},'%') or writer like concat('%',#{title},'%')")
    Page<Poem> GetPoembyTitle(String title);
@Select("select * from poem.rhesis where name like concat('%',#{title},'%') or fromm like concat('%',#{title},'%')")
    Page<RhesisDataVo> GetwriterB(String title);
@Select("select content from poem.potry where id=#{id}")
    String getcountbyid(int id);
@Update("UPDATE poem.userbookpoem SET reviewCount=reviewCount+1 WHERE book_id=(SELECT book_id FROM poem.userbook WHERE user_id=#{userid}) AND poem_id=#{poemid}")
    void update(Integer userid, Integer poemid);

    @Select("SELECT DISTINCT w.id, w.name, w.headImageUrl, w.simpleIntro, p.dynasty\n" +
            "        FROM poem.writer w\n" +
            "         JOIN poem.potry p ON w.name = p.writer and w.name like CONCAT('%',#{name},'%')")
    List<Writer> GetRondWriter11(String name);
@Select("SELECT * FROM poem.potry WHERE title LIKE CONCAT('%', #{content}, '%') OR potry.content LIKE CONCAT('%', #{content}, '%') order by case when title like CONCAT('%', #{content}, '%') THEN 1 else 2 end,title,content")
    List<PoemSerchVo> serch(String content);
}
