#include "a.h"
namespace test
{
int A::s_i=1;

A::A()
:m_ai(0)
,m_af(0.0f)
{
    
}

A::~A()
{
    
}

void A::funaa()
{
    m_ai=1;
    m_af=2.0f;
}

void A::funaa(int i)
{
    m_ai=1;
    m_af=2.0f;
}

void selfFun(int i,int j)
{
    i=i+j;
    i*=i;
    i*=j;
}

void A::funab()
{
    m_ai=3;
    m_af=4.0f;
}

void A::funac()
{
    int i=0;
    int j=1;
    m_ai=
    3;
    if(i>0){
        j=2;
    }
    else
        j=3;    
    m_af=4.0f;
}

}