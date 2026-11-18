package com.fuze.potryservice.mapper;


import com.fuze.dto.WriterDto;
import com.fuze.entity.Writer;
import com.fuze.vo.PoemDataVo;
import com.fuze.vo.PoemVo;
import com.fuze.vo.WriterVo;
import com.fuze.vo.WriterWithPoemsVo;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface WriterMapper {

    Integer getWriterCount();
    List<String> getAllWriterNames();
    List<PoemDataVo> selectPoemsByWriter(@Param("writer") String writer);
    WriterVo selectImageAndSimpleIntroByName(String name);
    String selectDetailIntroByName(String name);
    List<String> selectWritersByDynasty(String dynasty);

    /** 朝代诗人完整卡片(name+头像+简介): 一次SQL替代前端逐个N+1画像请求 */
    List<WriterVo> selectWritersByDynastyFull(@Param("dynasty") String dynasty);
    WriterWithPoemsVo selectWriterAndPoemsById(Long id);
    List<String> selectAllDynasties();
    PoemDataVo    selectFamousLinesByWriterId(Long id);
    List<WriterVo> selectAllWriters();
    List<WriterVo> selectRandomWriters();
    Writer add(WriterDto writer);
@Delete("delete from poem.writer where id=#{id}")
    void DeleteByid(Long id);
@Select("select * from poem.writer where id=#{id}")
    WriterVo getWriterById(int id);

    void save(WriterDto writerDto);

    List<WriterVo> getWriterByName(String name);

    List<Integer> selectAllWriterIds();

    List<String> selectWriterNamePrefix(@Param("kw") String kw);

    List<WriterVo> selectWritersByIds(@Param("ids") List<Integer> ids);

    List<Writer> selectWriterCardsByIds(@Param("ids") List<Integer> ids);
}