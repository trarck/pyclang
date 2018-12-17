#include "b.h"
#include "a.h"

B::B()
:m_bi(0)
,m_bf(0.0f)
{
    printf("in bbb ctor");
}

B::~B()
{
    
}

B::funba()
{
    m_bi=1;
    m_bf=2.0f;
    A a;
    a.funaa();
    a.m_ai=2;
}

B::funbb()
{
    m_bi=3;
    m_bf=4.0f;
}
