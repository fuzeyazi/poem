package com.fuze.potryservice.mapper;

import com.fuze.dto.WriterDto;
import com.fuze.entity.Writer;
import com.fuze.vo.PoemDataVo;
import com.fuze.vo.PoemVo;
import com.fuze.vo.WriterVo;
import com.fuze.vo.WriterWithPoemsVo;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface WriterMapper {

    Integer getWriterCount();
    List<String> getAllWriterNames();
    List<PoemDataVo> selectPoemsByWriter(@Param("writer") String writer);
    List<PoemDataVo> getRandomPoems();
    WriterVo selectImageAndSimpleIntroByName(String name);
    String selectDetailIntroByName(String name);
    List<String> selectWritersByDynasty(String dynasty);
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
}