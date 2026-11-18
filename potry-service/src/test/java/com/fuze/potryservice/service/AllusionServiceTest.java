package com.fuze.potryservice.service;

import com.fuze.potry.entity.Allusion;
import com.fuze.potryservice.mapper.AllusionMapper;
import com.fuze.potryservice.service.impl.AllusionServiceImpl;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("AllusionService & Caffeine Cache Unit Tests")
class AllusionServiceTest {

    @Mock
    private AllusionMapper allusionMapper;

    @InjectMocks
    private AllusionServiceImpl allusionService;

    private Allusion allusionZheLiu;
    private Allusion allusionDouKou;

    @BeforeEach
    void setUp() {
        allusionService.clearCache();

        allusionZheLiu = Allusion.builder()
                .id(1)
                .name("折柳")
                .pinyin("zhé liǔ")
                .dynasty("汉代")
                .origin("《三辅黄图·卷六·桥》")
                .originQuote("霸桥在长安东，跨水作桥。汉人送客至此桥，折柳赠别。")
                .story("古代长安霸桥两岸植柳。因柳与留谐音，古人送别时折柳相赠。")
                .relatedQuotes("李白《春夜洛城闻笛》：“此夜曲中闻折柳，何人不起故园情。”")
                .sentiment("惜别怀远")
                .status(1)
                .createTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .build();

        allusionDouKou = Allusion.builder()
                .id(2)
                .name("豆蔻")
                .pinyin("dòu kòu")
                .dynasty("唐代")
                .origin("杜牧《赠别二首·其一》")
                .originQuote("娉娉袅袅十三余，豆蔻梢头二月初。")
                .story("豆蔻初夏开花，比喻十三四岁少女的纯洁娇美与青春芳华。")
                .relatedQuotes("姜夔《扬州慢》：“二十四桥仍在，波心荡，冷月无声。”")
                .sentiment("青春芳华")
                .status(1)
                .createTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .build();
    }

    @Test
    @DisplayName("测试获取全量典故列表：首次未命中缓存查库，第二次命中 Caffeine L1 缓存")
    void testGetAllAllusions_CaffeineCacheHit() {
        when(allusionMapper.selectAllActive()).thenReturn(Arrays.asList(allusionZheLiu, allusionDouKou));

        // 第一次调用：Cache miss，查询 Mapper
        List<Allusion> result1 = allusionService.getAllAllusions();
        assertNotNull(result1);
        assertEquals(2, result1.size());
        assertEquals("折柳", result1.get(0).getName());
        verify(allusionMapper, times(1)).selectAllActive();

        // 第二次调用：Cache hit，直接从 Caffeine 内存读取，不应再调用 Mapper
        List<Allusion> result2 = allusionService.getAllAllusions();
        assertNotNull(result2);
        assertEquals(2, result2.size());
        verify(allusionMapper, times(1)).selectAllActive();
    }

    @Test
    @DisplayName("测试全量列表为空时的优雅返回")
    void testGetAllAllusions_Empty() {
        when(allusionMapper.selectAllActive()).thenReturn(Collections.emptyList());
        when(allusionMapper.selectList(null)).thenReturn(Collections.emptyList());

        List<Allusion> result = allusionService.getAllAllusions();
        assertNotNull(result);
        assertTrue(result.isEmpty());
    }

    @Test
    @DisplayName("测试根据ID获取典故：首次查询存入缓存，后续直接从缓存读取")
    void testGetAllusionById_CaffeineCacheHit() {
        when(allusionMapper.selectByIdDirect(1)).thenReturn(allusionZheLiu);

        // 首次查询
        Allusion firstCall = allusionService.getAllusionById(1);
        assertNotNull(firstCall);
        assertEquals("折柳", firstCall.getName());
        verify(allusionMapper, times(1)).selectByIdDirect(1);

        // 第二次查询相同 ID：命中 Caffeine 缓存
        Allusion secondCall = allusionService.getAllusionById(1);
        assertNotNull(secondCall);
        assertEquals("折柳", secondCall.getName());
        verify(allusionMapper, times(1)).selectByIdDirect(1);
    }

    @Test
    @DisplayName("测试根据名称获取典故：首次查询存入缓存，后续直接从缓存读取")
    void testGetAllusionByName_CaffeineCacheHit() {
        when(allusionMapper.selectByName("豆蔻")).thenReturn(allusionDouKou);

        // 首次查询
        Allusion firstCall = allusionService.getAllusionByName("豆蔻");
        assertNotNull(firstCall);
        assertEquals(2, firstCall.getId());
        assertEquals("豆蔻", firstCall.getName());
        verify(allusionMapper, times(1)).selectByName("豆蔻");

        // 第二次查询相同 Name：命中 Caffeine 缓存
        Allusion secondCall = allusionService.getAllusionByName("豆蔻");
        assertNotNull(secondCall);
        assertEquals("豆蔻", secondCall.getName());
        verify(allusionMapper, times(1)).selectByName("豆蔻");
    }

    @Test
    @DisplayName("测试清除缓存后，再次查询会重新触发 Mapper 查询")
    void testClearCache_RequeryDb() {
        when(allusionMapper.selectByIdDirect(1)).thenReturn(allusionZheLiu);

        // 首次查询入缓存
        allusionService.getAllusionById(1);
        verify(allusionMapper, times(1)).selectByIdDirect(1);

        // 清理缓存
        allusionService.clearCache();

        // 再次查询：应重新查 Mapper
        allusionService.getAllusionById(1);
        verify(allusionMapper, times(2)).selectByIdDirect(1);
    }

    @Test
    @DisplayName("测试无效参数（null或空值）输入时的防御性处理")
    void testBoundaryConditions() {
        assertNull(allusionService.getAllusionById(null));
        assertNull(allusionService.getAllusionByName(null));
        assertNull(allusionService.getAllusionByName(""));
        assertNull(allusionService.getAllusionByName("   "));
        verifyNoInteractions(allusionMapper);
    }
}
