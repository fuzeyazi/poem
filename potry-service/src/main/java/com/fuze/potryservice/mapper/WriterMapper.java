package com.fuze.potryservice.mapper;

import com.fuze.vo.PoemDataVo;
import com.fuze.vo.PoemVo;
import com.fuze.vo.WriterVo;
import com.fuze.vo.WriterWithPoemsVo;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

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
}